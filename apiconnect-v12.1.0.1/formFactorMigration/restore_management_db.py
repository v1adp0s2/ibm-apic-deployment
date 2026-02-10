# IBM Confidential
# OCO Source Materials
#
# (C) Copyright IBM Corporation 2021
# The source code for this program is not published or otherwise
# divested of its trade secrets, irrespective of what has been
# deposited with the U.S. Copyright Office.

import subprocess
import sys
import time
import argparse
import os
import shutil
import yaml
import base64
import random

oc_client = "oc"
kubectl_client = "kubectl"
client = oc_client

pwd = None
DATA_DIR = None
DATA_TEMP_DIR = None

CONFIG_FILE_NAME = "config.yaml"
config =  None
selectedMgmtSubsystemName = None

isCP4I = False
cloudAdminServer = None

mgmt_restore = {
  "apiVersion": "management.apiconnect.ibm.com/v1beta1",
  "kind": "ManagementRestore",
  "metadata": {
    "name": "TBD"
  },
  "spec" : {
    "backupName": "test"
  }
}

mgmt_edb_restore = {
  "apiVersion": "management.apiconnect.ibm.com/v1beta1",
  "kind": "ManagementRestore",
  "metadata": {
      "annotations": {
          "apiconnect-operator/management-db": "edb"
      },
    "name": "TBD"
  },
  "spec" : {
    "subsystemName": "TBD",
    "backupId": "TBD",
    "backup": {
        "host": "TBD",
        "path": "TBD",
        "credentials":"TBD"
    }
  }
}

targetSystemSpecVersion = None
targetSystemReconciledVersion = None

# runKubernetesCommand
def runKubernetesCommand(command, kubernetesNamespace, silent=False, retry=10, exitOnError=True):
    global client
    fullCommand = None
    
    if kubernetesNamespace == None:
        fullCommand = client + " " + command
    else:
        fullCommand = client + " -n " + kubernetesNamespace + " " + command 
    
    if not silent:
        print ("Kubernetes command : ", fullCommand)
        
    count = 0
    out = None
    err = None
    flag = True
    while flag:
        returnObject = subprocess.Popen(fullCommand, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        out, err = returnObject.communicate()        
    
        if (command == "version") and (returnObject.returncode != 0):
            print ("Failed to run kubernetes command [{c1}], error code {r1} and error message is [{e1}]".format(c1=fullCommand, r1=returnObject.returncode, e1=err))
            if kubernetesNamespace == None:
                fullCommand = kubectl_client + " " + command
            else:
                fullCommand = kubectl_client + " -n " + kubernetesNamespace + " " + command
            print ("Trying with kubectl and Command is : ", fullCommand)
            returnObject = subprocess.Popen(fullCommand, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
            out, err = returnObject.communicate()
            client = kubectl_client

        if returnObject.returncode == 0:
            flag = False
        else:
            if err != None: err = err.strip()
            if err != None and len(err) == 0: err = out
            if count < retry:
                count = count + 1
                time.sleep(15)
                print ("Retrying count {}. Command({}) failed with return code {} and error message : [[{}]]".format(count, fullCommand, returnObject.returncode, err))
            else:
                if exitOnError == True:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Failed to run the kubernetes command, [{}], return code {} and error is [[{}]].  Exiting...".format(fullCommand, returnObject.returncode, err)) 
                else:
                    out = err
                    flag = False  
    if not silent:
        print (out)
    return out

    
def runCommand(command, silent=False, retry=10, exitOnError=True):
    obfuscatedCommand = None
    if "--password" in command or "--apiKey" in command:
        if "--password" in command: obfuscatedCommand = command[0:command.index("--password")] + "--password ********"
        if "--apiKey" in command: obfuscatedCommand = command[0:command.index("--apiKey")] + "--apiKey ********"
    else:
        obfuscatedCommand = command

    print ("Command : ", obfuscatedCommand)
    
    count = 0
    out = None
    err = None
    flag = True
    while flag:
        returnObject = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        out, err = returnObject.communicate()
    
        if returnObject.returncode == 0:
            flag = False
        else:
            if err != None: err = err.strip()
            if err != None and len(err) == 0: err = out
            if count < retry:
                count = count + 1
                time.sleep(15)
                print ("Retrying count {}. Command({}) failed with return code {} and error message : [[{}]]".format(count, obfuscatedCommand, returnObject.returncode, err))
            else:
                if exitOnError == True:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Failed to run the command, [{}], return code {} and error is [[{}]].  Exiting...".format(obfuscatedCommand, returnObject.returncode, err)) 
                else:
                    out = err
                    flag = False  
    if not silent:
        print (out)
        print ()
    return out

#health check for portal and gateway of the target APIC system
def healthCheck(subsystem, ns):
    global targetSystemSpecVersion
    global targetSystemReconciledVersion
    if ns != None:
        out = runKubernetesCommand("get " + subsystem, ns)
        outList = out.splitlines()
        k = 0
        for each in outList:
            if k == 0:
                k = k + 1
                #skip header
                continue 
            subsystemName = each[0:each.index(" ")]
            print(subsystem + " subsystem name ::: " + subsystemName)
            crData = runKubernetesCommand("get " + subsystem + " " + subsystemName + " -o yaml", ns, True)
            crData = yaml.safe_load(crData)
            
            if subsystem == "mgmt":
                targetSystemSpecVersion = crData["spec"]["version"]
                targetSystemReconciledVersion = crData["status"]["versions"]["reconciled"]
            
            # check health
            print ("Phase : {} and state : {} for {} subsystem, {}".format(crData["status"]["phase"], crData["status"]["state"], subsystem, subsystemName))
            if not args.ignore_health_check:
                state = crData["status"]["state"]
                if crData["status"]["phase"] != "Running" or state[0:state.index("/")] != state[state.index("/") + 1:]:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Health check failed for {} subsystem with name {}. Phase : {} and state : {}".format(subsystem, subsystemName, crData["status"]["phase"], crData["status"]["state"]))
                print ("ACTION OUTPUT : {} with name {} is healthy".format(subsystem, subsystemName))
            print ()
    else:
        print ("ACTION OUTPUT : Skipping health check for {} subsytem as namespace is NOT provided in the input. Given namespace is {}".format(subsystem, ns))


def restoreManagementDatabase():
    global selectedMgmtSubsystemName
    print ("Restore management backup data::::")
    
    #get the saved configuration
    mgmtSubsystemNames = config["management_subsystem"].keys()
    managementSubsystemDetails = None
    selectedSubsystem = None
    if len(mgmtSubsystemNames) > 1:
        print ()
        print ("List of management subsystems from the saved configuration(source system) : ", list(mgmtSubsystemNames))
        
        if args.silent:
            selectedSubsystem = args.mgmt_subsystem_name
        else:
            selectedSubsystem = input("SELECT THE SUBSYSTEM FROM THE LIST : ")
        
        if selectedSubsystem != None: selectedSubsystem = selectedSubsystem.strip()
        if selectedSubsystem not in config["management_subsystem"]:
            if args.silent and selectedSubsystem == None:
                print("Multiple management subsystems found in the saved configuration. You need to select one by using -mgmt_subsys_name or --mgmt_subsystem_name flag")
            print ("Time when error occurred :", time.asctime())
            sys.exit("The selected subsystem({}) does not exist in the configuration. Exiting...".format(selectedSubsystem))
    
    elif len(mgmtSubsystemNames) == 1:
        selectedSubsystem = list(mgmtSubsystemNames)[0]
    
    if selectedSubsystem == None:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : No configuration found for the management subsystem from the source system.  Exiting...")
 
    print ("selected management subsystem from the source configuration : ", selectedSubsystem)
    selectedMgmtSubsystemName = selectedSubsystem
    
    print()
    managementSubsystemDetails = config["management_subsystem"][selectedSubsystem]
    sourceSystemReconciledVersion = managementSubsystemDetails["versionReconciled"]
    print ("Source system version : {}".format(sourceSystemReconciledVersion))
    print ("Target system version : {}".format(targetSystemReconciledVersion))
    print()
    if args.ignore_version_check == False and targetSystemReconciledVersion != None:
        if sourceSystemReconciledVersion.index("-") > 0:
            version1 = sourceSystemReconciledVersion[0:sourceSystemReconciledVersion.index("-")]
            if targetSystemReconciledVersion.startswith(version1) == False:
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : Target system version({}) does not match the soure system version({}).  Exiting...".format(targetSystemReconciledVersion, sourceSystemReconciledVersion))
    
    backupID = None
    if args.backup_id == None:
        if "backupId" not in managementSubsystemDetails:
            print ("Time when error occurred :", time.asctime())
            sys.exit("ERROR : Backup id not found in the management subsystem configuration.  Exiting...")
        backupID = managementSubsystemDetails["backupId"]
    else:
        print ("Using backup id provided in the -back_id or --backup_id flag.")
        backupID = args.backup_id
        
    #specific to crunchy postgres, but better we validate else restore will fail. revisit when other vendor comes
    if "pgclusterName" in managementSubsystemDetails:
        pgClusterNameFromSourceSystem = managementSubsystemDetails["pgclusterName"]
        print("Postgres cluster name in source system : {}".format(pgClusterNameFromSourceSystem))
        pgclusterNameFromTarget = runKubernetesCommand("get cluster --no-headers", args.mgmt_ns, True) # edb
        if pgclusterNameFromTarget != None and pgclusterNameFromTarget != "" and pgclusterNameFromTarget.lower().startswith("error") == False:
            pgclusterNameFromTarget = pgclusterNameFromTarget.splitlines()
            if len(pgclusterNameFromTarget) == 1:
                pgclusterNameFromTarget = pgclusterNameFromTarget[0][0:pgclusterNameFromTarget[0].index(" ")]
            else:
                for each_pg_name in pgclusterNameFromTarget:
                    each_pg_name = each_pg_name.strip()
                    if "keycloak" not in each_pg_name:
                        pgclusterNameFromTarget = each_pg_name[0:each_pg_name.index(" ")]
                        break

        print("Postgres cluster name in target system : {}".format(pgclusterNameFromTarget))
        if args.ignore_pgcluster_name == False and pgClusterNameFromSourceSystem != pgclusterNameFromTarget:
            print()
            print("While launching target management subsystem, you need to use the same value for siteName, management subsystem name, originalUID for DR to work. Try again.")
            print("Source system values, management subsystem name : {}, site name : {}, originalUID : {}".format(managementSubsystemDetails["name"], managementSubsystemDetails["siteName"], managementSubsystemDetails["originalUID"]))
            print("WARNING: Source system postgres cluster name and target system postgres cluster do not match. From v10.0.7 onwards(EDB postgres database), db restores should work fine. Proceeding....")
            # print ("Time when error occurred :", time.asctime())
            # sys.exit("ERROR : Restore will fail as the postgres cluster name is different in source({}) and target({}) APIC systems".format(pgClusterNameFromSourceSystem, pgclusterNameFromTarget))
    
    print()
    print ("Backup id from which management backup will be restored : " + backupID)
    
    # applicable only for crunchy based backups. 
    # if using edb, you cannot get list of source system backups using "k get backup" as the server name (management-0e88ecfa-db-2023-08-03T09:37:36Z) is different in target
    if "|" not in backupID:
        out = runKubernetesCommand("get managementbackups | grep Ready | grep full", args.mgmt_ns, False, 10)
        lines = out.splitlines()
        
        backFound = False
        backupName = None
        for eachLine in lines:
            if backupID in eachLine:
                backFound = True
                backupName = eachLine[0:eachLine.index(" ")]
                break
        if backFound == False:
            print ("Time when error occurred :", time.asctime())
            sys.exit("ERROR : No backup found from the list of management backups for the given backup id {}.  Exiting...".format(backupID))
        
        print ("Backup id : {} and backup name : {} ".format(backupID, backupName))
        print()

    #check if any existing management db restores are in running state, then wait
    flag = True
    loopCount = 0
    timeout = False
    while flag:
        loopCount = loopCount + 1
        if loopCount >= 60:
            flag = False
            print ("Timeout after Waiting for ALREADY running management db restores to be completed. current time : ", time.asctime())
            timeout = True
            break # safe break after 2 hr
        existingMgmtRestores = runKubernetesCommand("get managementrestore", args.mgmt_ns, True, 0, False)
        existingMgmtRestores = existingMgmtRestores.splitlines()
        currentRunningList = []
        for r1 in existingMgmtRestores:
            if "Running" in r1 or "Pending" in r1 or "RestoreInProgress" in r1 or "RestoreSuccessful" in r1 or "SFTPBackupDownloadSuccessful" in r1:
                currentRunningList.append(r1)

        if len(currentRunningList) == 0:
            flag = False
        else:
            print ("Waiting for ALREADY running management db restores to be completed. Current time : ", time.asctime())
            time.sleep(120)
    
    if timeout:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Timedout waiting for ALREADY running management db restores to be completed. Manually check the status of these restores , wait for them to complete and try again.")
    
    out = runKubernetesCommand("get mgmt", args.mgmt_ns, True)
    mgmtSubsystemNameInTarget = out.splitlines()[1]
    mgmtSubsystemNameInTarget = mgmtSubsystemNameInTarget[0:mgmtSubsystemNameInTarget.index(" ")]
    
    restoreCRName = "mgmt-restore-" + str(random.randint(0, 99999))
    restoreCRFileName = DATA_TEMP_DIR + "/" + restoreCRName + "_cr.yaml"

    if "|" not in backupID:
        mgmt_restore["metadata"]["name"] = restoreCRName
        mgmt_restore["spec"]["backupName"] = backupName
        with open(restoreCRFileName, 'w') as mgmtRestoreFile:
            yaml.dump(mgmt_restore, mgmtRestoreFile,  default_flow_style=False)
    else:
        mgmt_edb_restore["metadata"]["name"] = restoreCRName
        mgmt_edb_restore["spec"]["subsystemName"] = mgmtSubsystemNameInTarget
        mgmt_edb_restore["spec"]["backupId"] = backupID[0:backupID.index("|")]
        mgmt_edb_restore["spec"]["backup"]["host"] = managementSubsystemDetails["databaseBackup"]["host"]
        mgmt_edb_restore["spec"]["backup"]["path"] = managementSubsystemDetails["databaseBackup"]["path"] + "/" + backupID[backupID.index("|")+1:]
        mgmt_edb_restore["spec"]["backup"]["credentials"] = managementSubsystemDetails["databaseBackup"]["credentials"]
        mgmt_edb_restore["spec"]["backup"]["protocol"] = managementSubsystemDetails["databaseBackup"]["protocol"]
        if "port" in managementSubsystemDetails["databaseBackup"]:
            mgmt_edb_restore["spec"]["backup"]["port"] = managementSubsystemDetails["databaseBackup"]["port"]
        # support custom s3 settings
        if "backupCerts" in managementSubsystemDetails["databaseBackup"]:
            mgmt_edb_restore["spec"]["backup"]["backupCerts"] = managementSubsystemDetails["databaseBackup"]["backupCerts"]
        if "backups3URIStyle" in managementSubsystemDetails["databaseBackup"]:
            mgmt_edb_restore["spec"]["backup"]["backups3URIStyle"] = managementSubsystemDetails["databaseBackup"]["backups3URIStyle"]

        with open(restoreCRFileName, 'w') as mgmtRestoreFile:
            yaml.dump(mgmt_edb_restore, mgmtRestoreFile,  default_flow_style=False)
    
    print()
    print ("Performing restore ::")
    runKubernetesCommand("create -f " + restoreCRFileName, args.mgmt_ns)
    time.sleep(60)
    
    print ("Check status of currently running management restore cr::")
    restoreCRStatus = "INPROGRESS"
        
    flag = True
    loopCount = 0
    while flag:
        loopCount = loopCount + 1
        if loopCount >= 60:
            flag = False
            print ("Timeout after Waiting for management db restore.")
            break # safe break after 2 hr

        if restoreCRStatus == "INPROGRESS":
            res = runKubernetesCommand("get managementrestores " + restoreCRName + " -o yaml", args.mgmt_ns, True)
            if res != None and res != "" and res.lower().startswith("error") == False:
                res =  crData = yaml.safe_load(res)
                if res["status"]["phase"] == "Complete":
                    restoreCRStatus = res["status"]["phase"]
                    flag = False
                    print ("Management database restore completed for restore cr, " + restoreCRName)
                    break
        if flag:
            print ("Waiting for management database restore to be completed. Current time : ", time.asctime())
            time.sleep(120)
    
    print ()
    print ("Management database restore CR name : {} and status : {} ".format(restoreCRName, restoreCRStatus))
    if restoreCRStatus != "Complete":
        print("ERROR : Management restore NOT COMPLETE. Check the restore CR and api connect operator logs for details.")
        print("Try running the scripts again after checking the logs and identify the reason for restore failure.")
        print("Once management db restore is complete successfully and management subsystem is healthy, run the next steps.")
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : EXITING")

    if isCP4I and "restartedConfigurator" in config["management_subsystem"][selectedSubsystem]:
        config["management_subsystem"][selectedSubsystem]["restartedConfigurator"] = False
        print("ACTION OUTPUT : Updating restartedConfigurator to false in the config file as management db is restored successfully. cp4i installation and configurator job must run again.")
        with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
            yaml.dump(config, configFile, default_flow_style=False)

    print()
    print()
    print("Waiting for management subsystem to be healthy...    ")
    flag = True
    loopCount = 0
    timeout = False
    while flag:
        loopCount = loopCount + 1
        if loopCount >= 60:
            flag = False
            timeout = True
            print ("Timeout after Waiting 20 minutes for management subsytem to be healthy.")
            break # safe break after 20 minutes
        print ("Waiting for management subsystem to be healthy. Current time : ", time.asctime())
        time.sleep(20)
        crData = runKubernetesCommand("get mgmt " + mgmtSubsystemNameInTarget + " -o yaml", args.mgmt_ns, True)
        crData = yaml.safe_load(crData)
        state = crData["status"]["state"]
        if crData["status"]["phase"] == "Running" and state[0:state.index("/")] == state[state.index("/") + 1:]:
            print ("Management subsystem is healthy and restore is complete.")
            flag = False
            break
    print()

    if timeout == True:
        print("Timeout happened waiting for management subsystem to become healthy after db restore.")
        print("Check the health of management subsystem and operator logs.")
        print("Once management subsystem is healthy, run the next steps.")
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : EXITING")


def resetGateways():
    print("START resetGateways() : restart gateway pods")

    if args.gw_ns == None:
        args.gw_ns = args.mgmt_ns
    multipleNS = args.gw_ns.split("|")
    podInfo = {}
    for ns in multipleNS:
        output = runKubernetesCommand("get statefulsets -l app.kubernetes.io/component=datapower --no-headers", ns, True)
        if output != None and output != "" and output.lower().startswith("error") == False:
            output = output.splitlines()
            for eachLine in output:
                eachLine = eachLine.strip()
                stsName = eachLine[0:eachLine.index(" ")]
                pods = runKubernetesCommand("get pods | grep " + stsName, ns, True)
                if pods != None and pods != "" and pods.lower().startswith("error") == False:
                    pods = pods.splitlines()
                    for eachPod in pods:
                        eachPod = eachPod.strip()
                        podName = eachPod[0:eachPod.index(" ")]
                        runKubernetesCommand("delete pod " + podName, ns, False)
                        if ns in podInfo:
                            podInfo[ns].append(podName)
                        else:
                            podInfo[ns] = [podName]
    print("Waiting for 3 minutes for gateway pods to be ready. Current time : ", time.asctime())
    time.sleep(180)

    print(podInfo)
    flag = True
    loopCount = 0
    timeout = False
    while flag:
        loopCount = loopCount + 1
        if loopCount >= 30:
            flag = False
            print ("Timeout after Waiting for gateways to be healthy")
            timeout = True
            break # safe break after 30 min
        ready = True
        for eachNS in podInfo:
            gwPodNames = podInfo[eachNS]
            for eachGWPodName in gwPodNames:
                crData = runKubernetesCommand("get gw " + eachGWPodName + " -o yaml", eachNS, True, 0, False)
                if crData != None and crData != "" and crData.lower().startswith("error") == False:
                    crData = yaml.safe_load(crData)
                    if crData["status"]["phase"] != "Running":
                        ready = False
                        break
            if ready == False: break

        if ready:
            print("Gateway(s) are healthy.")
            flag = False
            break
        else:
            print ("Waiting for gateway pods to be ready. Current time : ", time.asctime())
            time.sleep(60)


def resetPortals():
    mgmtSubsystemNames = config["management_subsystem"].keys()
    if len(mgmtSubsystemNames) > 1:
        print ()
        print ("List of management subsystems from the saved configuration(source system) : ", list(mgmtSubsystemNames))

        if args.silent:
            selectedSubsystem = args.mgmt_subsystem_name
        else:
            selectedSubsystem = input("SELECT THE SUBSYSTEM FROM THE LIST : ")

        if selectedSubsystem != None: selectedSubsystem = selectedSubsystem.strip()
        if selectedSubsystem not in config["management_subsystem"]:
            if args.silent and selectedSubsystem == None:
                print("Multiple management subsystems found in the saved configuration. You need to select one by using -mgmt_subsys_name or --mgmt_subsystem_name flag")
            print ("Time when error occurred :", time.asctime())
            sys.exit("The selected subsystem({}) does not exist in the configuration. Exiting...".format(selectedSubsystem))
    elif len(mgmtSubsystemNames) == 1:
        selectedSubsystem = list(mgmtSubsystemNames)[0]

    managementSubsystemDetails = config["management_subsystem"][selectedSubsystem]

    portalServices = getGatewayOrPortalServices("portal")
    print()
    print()
    portalReset = False
    for eachEndpoint in portalServices:
        if "registered_portals" in managementSubsystemDetails:
            portalsFromSouceSystem = managementSubsystemDetails["registered_portals"]
            if eachEndpoint in portalsFromSouceSystem: #old portal entry
                continue

        print("Resetting registered portal service with name : ", portalServices[eachEndpoint])
        out = runCommand("apic factory-reset:delete --mode portaladmin --execute_reset true --server " + cloudAdminServer + " --portal_service_endpoint " + eachEndpoint, False, 0, False)
        print ("Portal factory resest output : [[" + out + "]]")
        print()
        if out != None and out.lower().startswith("error") == False:
            portalReset = True
            time.sleep(30)
        else:
            sys.exit("Portal reset for portal service with name {}, endpoint {} failed with error, {}. Exiting...".format(portalServices[eachEndpoint], eachEndpoint, out))

        if portalReset:
            print("Waiting for 3 minutes. Current time : ", time.asctime())
            print("ACTION OUTPUT : login to portal admin pod and confirm that all portal sites are deleted(command : list_sites) before proceeding further.")
            time.sleep(180)
        else:
            print("ACTION OUTPUT : No new registered portals in management subsystem or no data to reset on the portal subsystem for this portal.")
    print("\n")


def loginAndResetPortal():
    global cloudAdminServer
    adminPassword = None
    
    if isCP4I:
        out1 = runKubernetesCommand("get apiconnectcluster.apiconnect.ibm.com --no-headers", args.mgmt_ns, True)
        if out1 != None and out1 != "":
            out1 = out1.strip()
            topCRName = out1[0:out1.index(" ")]
            print("top cr name : ", topCRName)

            mgmtclusters = runKubernetesCommand("get mgmt --no-headers -o name", args.mgmt_ns, True)
            mgmtclusterList = []
            selectedMgmtName = None

            mgmtclusterOut = mgmtclusters.splitlines()
            for cluster in mgmtclusterOut:
                clusterName = cluster.split("/")[-1]
                mgmtclusterList.append(clusterName)
            
            if len(mgmtclusterList) > 1:
                print("Multiple management subsystems found in the target system : ", mgmtclusterList)
                selectedMgmtName = input("SELECT THE MANAGEMENT SUBSYSTEM FROM THE LIST : ")
            else:
                selectedMgmtName = mgmtclusterList[0]
            
            mgmtcrData = runKubernetesCommand("get mgmt " + selectedMgmtName + " -o yaml", args.mgmt_ns, True)
            mgmtcrData = yaml.safe_load(mgmtcrData)
            adminsecretName = mgmtcrData["spec"]["adminUser"]["secretName"]

            if args.password == None or args.password  == "":
                adminSecret = runKubernetesCommand("get secret " + adminsecretName + " -o yaml", args.mgmt_ns, False)
                adminSecret = yaml.safe_load(adminSecret)

                #saving to track the original value
                adminPassSecretFilename = DATA_TEMP_DIR + "/" + adminsecretName + "_step4.yaml"
                if os.path.exists(adminPassSecretFilename) == False:
                    with open(adminPassSecretFilename, 'w') as f1:
                        yaml.dump(adminSecret, f1, default_flow_style=False)
                adminPassword = adminSecret["data"]["password"]
                adminPassword = base64.b64decode(adminPassword.encode('ascii'))
                adminPassword = adminPassword.decode('ascii').strip()
            else:
                print("Using password from flag -password.")
                adminPassword = args.password
                #update topCRName-mgmt-admin-pass secret with the actual cloud manager admin password of cloud manager LUR
                encodedPassword = base64.b64encode(adminPassword.encode('ascii'))
                encodedPassword = encodedPassword.decode("ascii")
                runKubernetesCommand('patch secret ' + adminsecretName + ' --patch="{\\"data\\":{\\"password\\":\\"'+encodedPassword+'\\"}}"', args.mgmt_ns, False)
                print("ACTION OUTPUT : Updated secret(" + adminsecretName + " with cloud manager password after restoring database.")
    else:
        adminPassword = args.password


    if args.server == None:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Exiting. This is either CP4I instance or -reset_gateway_portal flag ise set. Hostname to connect to cloud manager is NOT provided. Need this to factory reset portal subsystem. Use flag --server or -s to provide the hostname and try again.")
    
    if adminPassword == None:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Exiting. This is either CP4I instance or -reset_gateway_portal flag ise set. admin password is needed to connect to cloud manager. Need this to factory reset portal subsystem. Use flag --password or -p to provide the password and try again.")

    runCommand("apic login --realm admin/default-idp-1 --username admin --server " + args.server + " --password '" + adminPassword + "'", False, 1)
    cloudAdminServer = args.server

    print("Calling resetPortals()")
    resetPortals()


def getGatewayOrPortalServices(serviceName):
    if serviceName != "gateway" and serviceName != "portal":
        print ("Time when error occurred :", time.asctime())
        sys.exit("Invalid service name provided. Valid values are gateway or portal.")
    output = {}
    orgs = runCommand("apic orgs:list --org_type=admin --fields id,name --server " + cloudAdminServer, True)
    orgs = yaml.safe_load(orgs)
    for org in orgs["results"]:
        azones = runCommand("apic availability-zones:list --fields id,name --server " + cloudAdminServer + " --org " + org["name"], True)
        azones = yaml.safe_load(azones)
        for azone in azones["results"]:
            services = runCommand("apic " + serviceName + "-services:list --fields name,endpoint --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
            services = yaml.safe_load(services)
            for service in services["results"]:
                output[service["endpoint"]] = service["name"]
    return output


def checkAndApplyCP4ICredsSecret():
    if "cp4i_registration_secret" in config["management_subsystem"][selectedMgmtSubsystemName]:
        print("Applying the same source system cp4i registration secret (topcr-cp4i-secret) on the target cp4i system.")
        cp4iCredsSecretName = runKubernetesCommand("get secret | grep cp4i-creds", args.mgmt_ns)
        if cp4iCredsSecretName != None and cp4iCredsSecretName != "":
            cp4iCredsSecretName = cp4iCredsSecretName.strip()
            cp4iCredsSecretName = cp4iCredsSecretName[0:cp4iCredsSecretName.index(" ")]
            srcFile = DATA_DIR + "/" + selectedMgmtSubsystemName + "/" + config["management_subsystem"][selectedMgmtSubsystemName]["cp4i_registration_secret"]
            targetFile = DATA_TEMP_DIR + "/" + cp4iCredsSecretName+".yaml"
            shutil.copyfile(srcFile, targetFile)

            # change secret name to what is used in the target
            cp4i_creds_secret = None
            if os.path.exists(targetFile):
                text_file3 = open(targetFile, "r")
                c3 = text_file3.read()
                cp4i_creds_secret = yaml.safe_load(c3)
                cp4i_creds_secret["metadata"]["name"] = cp4iCredsSecretName
                text_file3.close()
            with open(DATA_TEMP_DIR + "/" + cp4iCredsSecretName+".yaml", 'w') as updatedFile:
                yaml.dump(cp4i_creds_secret, updatedFile, default_flow_style=False)
            runKubernetesCommand("apply -f " + targetFile, args.mgmt_ns)


def validateNamespaces(listOfInputNamespaces):
    namespaceOutput = runKubernetesCommand("get ns", None, True)
    namespaceOutput = namespaceOutput.splitlines()
    existingNamespaceList = []
    skipHeader = True
    for x in namespaceOutput:
        if skipHeader == True:
            skipHeader = False
            continue
        existingNamespaceList.append(x[0:x.index(" ")])
    #print ("Valid namespaces are : ", existingNamespaceList)
    print()
        
    for eachGivenNS in listOfInputNamespaces:
        if eachGivenNS != None:
            giveNamespacesforSubsys = None
            giveNamespacesforSubsys = eachGivenNS.split("|")
            for each in giveNamespacesforSubsys:
                if each != "" and each not in existingNamespaceList:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Invalid namespace, {} provided. Namespace(s) given as input for this subsystem : {}. Exiting...".format(each, eachGivenNS))


# start
def start():
    global isCP4I
    print ("CHECKING IF KUBECTL/OC EXIST IN THE PATH AND HAVE ACCESS TO THE CLUSTER :")
    runKubernetesCommand("version", "default")
    
    if args.skip_namespace_validation == False:
        validateNamespaces([args.mgmt_ns])

    if args.cp4i:
        isCP4I = True
        print("CP4I flag provided in the script.")
    else:
        #is this correct way?
        out = runKubernetesCommand("get crd | grep cp4i.ibm.com", "default", True, 1, False)
        print("check for cp4i.ibm.com api group")
        if out != None and out != "" and "cp4i.ibm.com" in out:
            isCP4I = True
    print("ACTION OUTPUT : is CP4I :", isCP4I)

    print()
    if isCP4I or args.reset_gateway_portal:
        loginAndResetPortal()
    
    if args.mgmt_ns == None or args.mgmt_ns == "" or  "|" in args.mgmt_ns:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Invalid namespace({}) provided for management subsystem. Only one namespace need to be provided. Exiting...".format(args.mgmt_ns))
    print("Checking health of management subsystem")
    healthCheck("mgmt", args.mgmt_ns)

    print("Restoring management backup from source system")
    restoreManagementDatabase()
    
    if isCP4I: 
        checkAndApplyCP4ICredsSecret()

    if isCP4I or args.reset_gateway_portal:
        #restart gw pods after management db restore
        resetGateways()
    
    print()
    print()
    print("This script performed the following actions in the target APIC system:")
    print("**********************************************************************")
    print("1. Checked the health of the manageemnt subsystem in the target APIC subsystem.")
    print("2. Restored the management database backup that was taken from the source APIC system.")
    print()
    print("Next steps:")
    print("1. Run the register_gateway_portals_in_target.py script to create the new gateways and portals using the mapping between old and new endpoints.")
    print("    -  Two ways to run the register_gateway_portals_in_target.py script")
    print("    -  Interactive mode : Prompts the user to enter the new endpoints corresponding to the old endpoints from gateway and portal.")
    print("    -  Silent mode : Using the -silent flag and the gateway_portal_mapping.yaml containing mapping between old and new endpoints. Correct values must be present in the yaml file.")
    print()
                	
    
    
    
	
parser = argparse.ArgumentParser(description="The script is used in form factor to form factor migration to restore a backup from source system management database\n\
into the target system management database. Users can restore using this script or using the management restore CR in api connect.\n \n\
Prerequisites ::\n\
1. Access to the cluster(target system) using kubectl or oc,\n\
2. Python 3.x and PyYAML module need to be installed\n\
3. This script must be run on the target APIC system after the management subsystem is up and running.\n\
4. The data directory where the configuration from the source system are saved. The data directory with source configuration must be present in the same directory as this script." , 
formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument("-n", "--namespace", dest = "ns", help="uses this namespace value for all subsystems if individual subsystem namespace is not provided.")
parser.add_argument("-mgmt_ns", "--management_namespace", dest = "mgmt_ns", help="namespace of the management subsystem. This has more precedence than the common flag, -n or --namespace.")

parser.add_argument("-gw_ns", "--gateway_namespace", dest = "gw_ns", help="namespace of the gateway subsystems. Used to reset gateway susbsystems when they are in multiple namespacces. If not privded, it is assumed the gateways are present in same namespace as management subsystem.")
parser.add_argument("-s", "--server", dest = "server", help="hostname to connect to cloud manager. Use platform api hostname. This is needed to need to factory reset portal subsystems.")
parser.add_argument("-p", "--password", dest = "password", help="password to connect to cloud manager using admin user. This is needed to factory reset portal subsystems when Kubernetes (only when you want to laod data after registration) is the target cluster. By default this is not needed and will be read from secret(TOPCR--mgmt-admin-pass) created during CP4I isntall. This is only needed when you ran restore_management_db.py script multiple times and admin password is different than the value set in secret(TOPCR--mgmt-admin-pass)")
parser.add_argument('-reset_gateway_portal', "--reset_gateway_portal", action='store_true', dest = "reset_gateway_portal", help='Restart gateway pods and factory reset portal subsystems.')

parser.add_argument('-ignore_health_check', "--ignore_health_check", action='store_true', dest = "ignore_health_check", help='ignores health check status for each subsystem and proceeds.')
parser.add_argument('-backup_id', "--backup_id", dest = "backup_id", help='The backup id of the management database that will be restored on the target management subsystem. This flag has more precedence than the backup id generated when save source configuration script was run on the source system. If backup (EDB postgres database) is from v10.0.7.0 or later version , it should be of the format 20230808T211342|management-0e88ecfa-db-2023-08-03T09:37:36Z')

parser.add_argument('-skip_namespace_validation', "--skip_namespace_validation",  action='store_true', dest = "skip_namespace_validation", help='Skips validation of input namespaces.')

parser.add_argument('-ignore_pgcluster_name', "--ignore_pgcluster_name", action='store_true', dest = "ignore_pgcluster_name", help='Does not validate the pg cluster name with source value. For restore to succeed, the postgres cluster name must be same in both source and target APIC system')
parser.add_argument('-ignore_version_check', "--ignore_version_check", action='store_true', dest = "ignore_version_check", help='ignores version match between source and target systems.')

parser.add_argument('-silent', "--silent", action='store_true', dest = "silent", help='Does not prompt for additinal inputs and proceeds silently.')
parser.add_argument('-mgmt_subsys_name', "--mgmt_subsystem_name", dest = "mgmt_subsystem_name", help='If multiple management subsytems present in the configuration, the script will use this.')
parser.add_argument("-cp4i", "--cp4i",  action='store_true', dest = "cp4i", help="It is Cloud Pak for Integration cluster.")

args = parser.parse_args()

print ("Start time :", time.asctime())
print ()

print ("Input namespace provided for all subsystems (-n or --namespace flag) : ", args.ns)
print ("Input namespace provided for management subsystem (-mgmt_ns or --management_namespace flag) : ", args.mgmt_ns)
print ()

print ("hostname to connect to cloud manager(-s or --server flag) : ", args.server)
print ()

print ("Ignore health check status for each subsystem (-ignore_health_check or --ignore_health_check flag) : ", args.ignore_health_check)
print ("Ignore version match check (-ignore_version_check or --ignore_version_check flag) : ", args.ignore_version_check)
print ()

print ("silent (-silent or --silent flag) : ", args.silent)
print ("Mangement subsystem name (-mgmt_subsys_name or --mgmt_subsystem_name flag) : ", args.mgmt_subsystem_name)
print ("is CP4I installation (-cp4i or --cp4i flag) : ", args.cp4i)
print ()

pwd = os.getcwd()
DATA_DIR = pwd + "/data"
DATA_TEMP_DIR = pwd + "/data/temp"

if args.mgmt_ns == None:
    print ("Management namespace (-mgmt_ns or --management_namespace flag) not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.mgmt_ns = args.ns

if args.mgmt_ns == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Namespace for the management subsystem not provided . Exiting...")


# load config data if exists
if os.path.exists(DATA_DIR + "/" + CONFIG_FILE_NAME):
    print ("Source APIC system configuration file exists. Loading it")
    text_file = open(DATA_DIR + "/" + CONFIG_FILE_NAME, "r")
    config1 = text_file.read()
    print("Configuration file : ", config1)
    config = yaml.safe_load(config1)
    text_file.close()
else:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : config.yaml file with details of the source APIC system in NOT present in the data directory. Exiting...")

start();

print()
print ("End time :", time.asctime())