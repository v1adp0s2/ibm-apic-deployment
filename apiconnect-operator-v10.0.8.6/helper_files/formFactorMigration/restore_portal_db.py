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
import random
import yaml

oc_client = "oc"
kubectl_client = "kubectl"
client = oc_client

pwd = None
DATA_DIR = None
DATA_TEMP_DIR = None

CONFIG_PORTAL_FILE_NAME = "config_portal.yaml"
config_portal = None

ptl_restore = {
  "apiVersion": "portal.apiconnect.ibm.com/v1beta1",
  "kind": "PortalRestore",
  "metadata": {
    "name": "TBD"
  },
  "spec" : {
    "type": "site",
    "portalCluster": "portal",
    "siteName": "TBD",
    "customUrl": "TBD"
  }
}


ptl_system_restore = {
  "apiVersion": "portal.apiconnect.ibm.com/v1beta1",
  "kind": "PortalRestore",
  "metadata": {
    "name": "TBD"
  },
  "spec" : {
    "type": "system",
    "portalCluster": "portal",
    "systemName": "TBD"
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

#health check for portal and gateway of the target apic system
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


def restorePortalDatabase():
    print ("Restore portal sites ::")
    
    #get the saved configuration
    portalSubsystemNames = config_portal["portal_subsystem"].keys()
    portalSubsystemDetails = None
    selectedSubsystem = None
    if len(portalSubsystemNames) > 1:
        print ()
        print ("List of portal subsystems from the saved configuration(source system) : ", list(portalSubsystemNames))
        
        if args.silent:
            selectedSubsystem = args.ptl_subsystem_name
        else:
            selectedSubsystem = input("SELECT THE SUBSYSTEM FROM THE LIST : ")
        
        if selectedSubsystem != None: selectedSubsystem = selectedSubsystem.strip()
        if selectedSubsystem not in config_portal["portal_subsystem"]:
            if args.silent and selectedSubsystem == None:
                print("Multiple portal subsystems found in the saved configuration. You need to select one by using -ptl_subsys_name or --ptl_subsystem_name flag")
            print ("Time when error occurred :", time.asctime())
            sys.exit("The selected subsystem({}) does not exist in the configuration. Exiting...".format(selectedSubsystem))
    
    elif len(portalSubsystemNames) == 1:
        selectedSubsystem = list(portalSubsystemNames)[0]
    
    if selectedSubsystem == None:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : No configuration found for the portal subsystem from the source system.  Exiting...")
 
    print ("selected portal subsystem from the source configuration : ", selectedSubsystem)
    print()
    print()

    portalSubsystemDetails = config_portal["portal_subsystem"][selectedSubsystem]
    portalSiteBackupsToBeRestored = portalSubsystemDetails["backupId_sites"]

    print ("Site backup ids to be restored : ", portalSiteBackupsToBeRestored)
    

    loopCount = 0
    backupsFound = None
    while True:
        allPortalBackups = runKubernetesCommand("get portalbackups.portal.apiconnect.ibm.com | grep Ready", args.ptl_ns, True)
        allPortalBackups = allPortalBackups.splitlines()

        #N*N live with it
        #both for v10-v10 and v2018-v10
        backupsFound = []
        for eachFromAllBackups in allPortalBackups:
            eachBackupId = eachFromAllBackups.split()[1]
            for eachPortalBackupToBeRestored in portalSiteBackupsToBeRestored:
                if eachBackupId in eachPortalBackupToBeRestored:
                    backupsFound.append(eachPortalBackupToBeRestored)
        loopCount = loopCount + 1
        if len(backupsFound) == len(portalSiteBackupsToBeRestored) or loopCount > 10:
            break
        else:
            print ("Not able to find portal backups. Will wait and retry. Current time : ", time.asctime())
            time.sleep(180)

    if len(backupsFound) != len(portalSiteBackupsToBeRestored):
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Some backups saved in the configuration were NOT found in the list of portal backups in the target APIC system. If there are a large number of backups present on the backup server consider moving the older backups to another location. Backups found : {}".format(backupsFound))
    else:
        print("ACTION OUTPUT : All site backups listed above exist.")
    
    #used when onlyv v10-v10 was supported
    #allBackupsExist = True
    #missingBackup = None
    #for eachPortalBackupToBeRestored in portalSiteBackupsToBeRestored:
    #    backupFound = False
    #    for eachFromAllBackups in allPortalBackups:
    #        if eachPortalBackupToBeRestored in eachFromAllBackups:
    #            backupFound = True
    #            break
    #    if backupFound == False:
    #        missingBackup = eachPortalBackupToBeRestored
    #        allBackupsExist = False
    #        break
    #if allBackupsExist == False:
    #    print ("Time when error occurred :", time.asctime())
    #    sys.exit("ERROR : BackupId, {} from the saved configuration of source portal NOT found in the list of portal backups in target APIC system.  Exiting...".format(missingBackup))
    #else:
    #    print("All site backups listed above exist.")

    out = runKubernetesCommand("get ptl", args.ptl_ns, True)
    ptlSubsystemNameInTarget = out.splitlines()[1]
    ptlSubsystemNameInTarget = ptlSubsystemNameInTarget[0:ptlSubsystemNameInTarget.index(" ")]
    print ("ACTION OUTPUT : ptlSubsystemNameInTarget : ", ptlSubsystemNameInTarget)
    print()

    #system backup, added this to support DR when moving fro cp4i to ocp. platform api changes
    if args.server != None:
        print()
        print()
        print("ACTION OUTPUT : Platform api hostname is provided in the input. Performing portal system restore")
        restoreCRName = "prsystem" + "-" + str(random.randint(0, 99999))
        ptl_system_restore["metadata"]["name"] = restoreCRName
        ptl_system_restore["spec"]["portalCluster"] = ptlSubsystemNameInTarget
        ptl_system_restore["spec"]["systemName"] = portalSubsystemDetails["backupId_system"]
        if args.server != None and args.server != "":
            ptl_system_restore["spec"]["customPlatformApiHostname"] = args.server + "/api"
            print("customPlatformApiHostname in the portal system restore : ", ptl_system_restore["spec"]["customPlatformApiHostname"])
        restoreCRFileName = DATA_TEMP_DIR + "/" + restoreCRName + "_cr.yaml"
        with open(restoreCRFileName, 'w') as ptlRestoreFile:
            yaml.dump(ptl_system_restore, ptlRestoreFile,  default_flow_style=False)
        runKubernetesCommand("create -f " + restoreCRFileName, args.ptl_ns)


    print()
    #check if any existing restores are in running state, then wait
    flag = True
    loopCount = 0
    timeout = False
    while flag:
        loopCount = loopCount + 1
        if loopCount >= 60:
            flag = False
            print ("Timeout after Waiting for already running portal site restores to be completed.")
            timeout = True
            break # safe break after 2 hr
        existingPortalRestores = runKubernetesCommand("get portalrestores", args.ptl_ns)
        existingPortalRestores = existingPortalRestores.splitlines()
        currentRunningList = []
        for r1 in existingPortalRestores:
            if "Running" in r1 or "Pending" in r1:
                currentRunningList.append(r1)

        if len(currentRunningList) == 0:
            flag = False
        else:
            print ("Waiting for already running portal system/site restores to be completed. Current time : ", time.asctime())
            time.sleep(120)
    
    if timeout:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Timedout waiting for already running portal site restores to be completed. Manually check the status of these restores and try again.")
    

    print()
    print()
    restoreCRMap = {}
    if "backupInfo" in portalSubsystemDetails:
        j = 1
        for eachBackupId in portalSubsystemDetails["backupInfo"]:
            restoreCRName = "pr" + str(j) + "-" + str(random.randint(0, 99999))
            fileNameAndURL = portalSubsystemDetails["backupInfo"][eachBackupId]
            print (str(j) + ". Restoring portal backup : {} site url : {} ".format(eachBackupId, fileNameAndURL[fileNameAndURL.index("|")+1:]))
            
            confirm = "no"
            if args.skip_restore_confirm_check:
                confirm = "yes"
            else:
                confirm = input("Do you want to perform portal restore for this site, type yes to confirm : ")
                if confirm != None: confirm = confirm.strip()
                confirm = confirm.lower()
            
            if (confirm == "yes"):

                print ("Portal restore CR name : {}".format(restoreCRName))
                ptl_restore["metadata"]["name"] = restoreCRName
                ptl_restore["spec"]["portalCluster"] = ptlSubsystemNameInTarget
                ptl_restore["spec"]["siteName"] = fileNameAndURL[0:fileNameAndURL.index("|")]
                ptl_restore["spec"]["customUrl"] = fileNameAndURL[fileNameAndURL.index("|")+1:]

                restoreCRFileName = DATA_TEMP_DIR + "/" + restoreCRName + "_cr.yaml"
                with open(restoreCRFileName, 'w') as ptlRestoreFile:
                    yaml.dump(ptl_restore, ptlRestoreFile,  default_flow_style=False)
                runKubernetesCommand("create -f " + restoreCRFileName, args.ptl_ns)
                restoreCRMap[eachBackupId] = restoreCRName + ":Running"
                time.sleep(5)
                j = j + 1
                #commenting block as https://github.ibm.com/apimesh/devportal/issues/7974 is fixed now
                ################################################################################################
                #work around for portal restore issue : wait for each restore to complete before start the next one
                #sequential running of portal restores
                #remove/comment this block once portal fixes the issue
                #flag = True
                #loopCount = 0
                #timeout = False
                #while flag:
                #    loopCount = loopCount + 1
                #    if loopCount >= 30:
                #        flag = False
                #        print ("Timeout after Waiting for portal site restore using restore cr name : ", restoreCRName)
                #        timeout = True
                #        break # safe break after 1 hr
                #    completed = False
                #    res = runKubernetesCommand("get portalrestores " + restoreCRName + " -o yaml", args.ptl_ns, True, 0, False)
                #    status = None
                #    if res != None and res != "" and res.lower().startswith("error") == False:
                #        res =  crData = yaml.safe_load(res)
                #        status = None
                #        if "status" in res and "phase" in res["status"]: 
                #            status = res["status"]["phase"]
                #        if status == "Ready" or status == "Failed":
                #            restoreCRMap[eachBackupId] = restoreCRName + ":" + status
                #            completed = True

                #    if completed:
                #        print("ACTION OUTPUT : Portal restore COMPLETED with status : {} for restore cr  : {}  \n\n".format(status, restoreCRName))
                #        flag = False
                #        break
                #    else:
                #        print ("Waiting for portal site restore to be completed, current status : [{}], check every 2 minutes. Current time : {} ".format(status, time.asctime()))
                #        time.sleep(120)

                #if timeout == True:
                #    print("ACTION OUTPUT :Timedout waiting for portal restore to be completed. Check the portal site restore status manually.")
                #    print("ACTION OUTPUT : Restore the remaining sites manually or try running the script once again.")
                #    print ("Time when error occurred :", time.asctime())
                #    sys.exit("ERROR : EXITING")
                ################################################################################################
            else:
                restoreCRMap[eachBackupId] = "SKIPPED RESTORE"
                j = j + 1
    else:
        print ("Time when error occurred :", time.asctime())
        sys.exit("Backup info (site backup file name, new url) for the portal site backups not found in the portal configuration. Exiting...")


    print()
    print()
    flag = True
    loopCount = 0
    timeout = False
    while flag:
        loopCount = loopCount + 1
        if loopCount >= 90:
            flag = False
            print ("Timeout after Waiting for portal site restore.")
            timeout = True
            break # safe break after 3 hr
        print()
        allCompleted = True
        for backupId in restoreCRMap:
            eachRunningRestore = restoreCRMap[backupId]
            if eachRunningRestore != "SKIPPED RESTORE":
                eachRunningRestoreName = eachRunningRestore[0:eachRunningRestore.index(":")]
                eachRunningRestoreStatus = eachRunningRestore[eachRunningRestore.index(":")+1:]
                if eachRunningRestoreStatus == "Running":
                    res = runKubernetesCommand("get portalrestores " + eachRunningRestoreName + " -o yaml", args.ptl_ns, True, 0, False)
                    if res != None or res.startswith("Error") == False:
                        res =  crData = yaml.safe_load(res)
                        if res["status"]["phase"] == "Ready":
                            restoreCRMap[backupId] = eachRunningRestoreName + ":Ready"
                            print ("Portal site restore COMPLETED SUCCESSFULLY for backup id : {} using restore cr name : {}".format(backupId, eachRunningRestoreName))
                        elif res["status"]["phase"] == "Failed":
                            restoreCRMap[backupId] = eachRunningRestoreName + ":Failed"
                            print ("Portal site restore FAILED for backup id : {} using restore cr name : {}".format(backupId, eachRunningRestoreName))
                        else:
                            print ("Portal site backup id : {}, restore CR : {} and status : {}".format(backupId, eachRunningRestoreName, res["status"]["phase"]))
                            allCompleted = False
                        print()
                    else:
                        print ("portal restore response value : ", res)
                        allCompleted = False
        
        if allCompleted:
            flag = False
            break
        else:
            print ("Waiting for portal site restore to be completed, check every 2 minutes. Current time : ", time.asctime())
            time.sleep(120)
  

    print()
    k = 1
    flag1 = True
    print("Portal restore status:")
    for eachBackupId in portalSubsystemDetails["backupInfo"]:
        if eachBackupId in restoreCRMap:
            if "SKIPPED" in restoreCRMap[eachBackupId]:
                print(str(k) + ". Backup Id : {} and status : SKIPPED RESTORE".format(eachBackupId))
            else:
                if ":Ready" not in restoreCRMap[eachBackupId]: flag1 = False
                print(str(k) + ". Backup Id : {} and CR name and status   :   {}".format(eachBackupId, restoreCRMap[eachBackupId]))
        else:
            flag1 = False
            print(str(k) + ". Backup Id : {} and status : NOT_STARTED".format(eachBackupId))
        k = k + 1


    if timeout == True:
        print("ACTION OUTPUT : Timeout happened during portal site restore or while subsystem coming back to healthy state")
        print("ACTION OUTPUT : Check the portal site restore status manually and also the health of the portal subsystem.")
        print("ACTION OUTPUT : Once portal sites are restored and portal is healthy, run the next steps.")
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : EXITING")

    print()
    print()
    out = runKubernetesCommand("get ptl", args.ptl_ns, True)
    ptlSubsystemNameInTarget = out.splitlines()[1]
    ptlSubsystemNameInTarget = ptlSubsystemNameInTarget[0:ptlSubsystemNameInTarget.index(" ")]
    flag = True
    timeout = False
    loopCount = 0
    while flag:
        loopCount = loopCount + 1
        if loopCount >= 60:
            flag = False
            timeout = True
            print ("Timeout after Waiting for portal subsytem to be healthy. Current time : ", time.asctime())
            break # safe break after 30 minutes
        crData = runKubernetesCommand("get ptl " + ptlSubsystemNameInTarget + " -o yaml", args.ptl_ns, True)
        crData = yaml.safe_load(crData)
        state = crData["status"]["state"]
        if crData["status"]["phase"] == "Running" and state[0:state.index("/")] == state[state.index("/") + 1:]:
            if flag1 == False:
                print ("ACTION OUTPUT : Some of the restore crs are NOT REady. Check the logs and try restoring manually.")
            else:
                print ("ACTION OUTPUT : Restore is completed successfully and subsystem is healthy.")
            flag = False
            break
        print ("Waiting for portal subsystem to be healthy. Current time : ", time.asctime())
        time.sleep(30)
    
    if timeout == True:
        print("ACTION OUTPUT : Timeout happened while waiting for portal subsystem to be healthy")
        print("ACTION OUTPUT : Check portal subsystem status and pod/operator logs.")
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : EXITING")

    print()
    print()
    print("This script performed the following actions in the target APIC system:")
    print("**********************************************************************")
    print("1. Checked the health of the portal subsystem.")
    if flag1 == False:
        print("2. Some of the portal restores NOT Ready. Check the report above and try restoring the portal sites manually before proceeding with next steps.")
    else:
        print("2. Restored the backup for portal sites that were taken from the source APIC system.")
    print()
    print("Next steps:")
    print("1. Run the update_to_new_gateways.py script to update the gateway information in every space/catalog/provider_org to point to the new gateways.")
    print("    -  Two ways to run the update_to_new_gateways.py script")
    print("    -  Interactive mode : Prompts the user to enter credentials for every provider org.")
    print("    -  Silent mode : Using the -silent flag and the provider_org_credentials.yaml file containing the credentials for every provider org. Check the yaml for correct credentials before running the script.")
    print()


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
    print ("CHECKING IF KUBECTL/OC EXIST IN THE PATH AND HAVE ACCESS TO THE CLUSTER :")
    runKubernetesCommand("version", "default")
    
    if args.skip_namespace_validation == False:
        validateNamespaces([args.ptl_ns])
    
    if args.ptl_ns == None or args.ptl_ns == "" or "|" in args.ptl_ns:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Invalid namespace({}) provided for portal subsystem. Only one namespace need to be provided. Exiting...".format(args.ptl_ns))
    
    healthCheck("ptl", args.ptl_ns)
    restorePortalDatabase()
                	
    
    
    
	
parser = argparse.ArgumentParser(description="The script is used in form factor to form factor migration to restore a portal site backups from source system\n\
into the target system. Users can restore portal sites using this script or using the portal restore CR or directly from portal pod in api connect.\n \n\
Prerequisites ::\n\
1. Access to the cluster(target system) using kubectl or oc,\n\
2. Python 3.x and PyYAML module need to be installed\n\
3. This script must be run on the target APIC system after updating portals in each provider org(using the update_to_new_portals.py script).\n\
4. The data directory where the configuration from the source system are saved. The data directory with source configuration must be present in the same directory as this script." , 
formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument("-n", "--namespace", dest = "ns", help="uses this namespace value for all subsystems if individual subsystem namespace is not provided.")
parser.add_argument("-ptl_ns", "--portal_namespace", dest = "ptl_ns", help="namespace of the portal subsystem. This has more precedence than the common flag, -n or --namespace.")

# added in 10.0.5.3, need this in portal restore CR for DR scenarios (cp4i to ocp with same endpoints)
parser.add_argument("-s", "--server", dest = "server", help="hostname to connect to cloud manager. Use platform api hostname. Use this property only for DR scenario where endpoints wont change. This is needed if performing DR from CP4I to OCP. If endpoints are changing and you set this property, portal system restore will fail.")

parser.add_argument('-ignore_health_check', "--ignore_health_check", action='store_true', dest = "ignore_health_check", help='ignores health check status for each subsystem and proceeds.')

parser.add_argument('-skip_namespace_validation', "--skip_namespace_validation",  action='store_true', dest = "skip_namespace_validation", help='Skips validation of input namespaces.')

parser.add_argument('-silent', "--silent", action='store_true', dest = "silent", help='Does not prompt for additinal inputs and proceeds silently.')
parser.add_argument('-ptl_subsys_name', "--ptl_subsystem_name", dest = "ptl_subsystem_name", help='If multiple portal subsytems present in the configuration, the script will use this.')
parser.add_argument('-skip_restore_confirm_check', "--skip_restore_confirm_check", action='store_true', dest = "skip_restore_confirm_check", help='Skips asking form confirmatiion for each portal site and restores all portal sites.')


args = parser.parse_args()

print ("Start time :", time.asctime())
print ()

print ("Input namespace provided for all subsystems (-n or --namespace flag) : ", args.ns)
print ("Input namespace provided for portal subsystem (-ptl_ns or --portal_namespace flag) : ", args.ptl_ns)
print ("Host name to connect to cloud manager(-s or --server flag) : ", args.server)
print ()

print ("Ignore health check status for each subsystem (-ignore_health_check or --ignore_health_check flag) : ", args.ignore_health_check)
print ()

print ("silent (-silent or --silent flag) : ", args.silent)
print ("Portal subsystem name (-ptl_subsys_name or --ptl_subsystem_name flag) : ", args.ptl_subsystem_name)
print ("Skip portal restore confirmation check (-skip_restore_confirm_check or --skip_restore_confirm_check flag) : ", args.skip_restore_confirm_check)

pwd = os.getcwd()
DATA_DIR = pwd + "/data"
DATA_TEMP_DIR = pwd + "/data/temp"

if args.ptl_ns == None:
    print ("Portal namespace (-ptl_ns or --portal_namespace flag) not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.ptl_ns = args.ns

if args.ptl_ns == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Namespace for the portal subsystem not provided . Exiting...")


# load config data if exists
if os.path.exists(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME):
    print ("Source APIC ystem portal configuration file exists. Loading it")
    text_file = open(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME, "r")
    config1 = text_file.read()
    print("Portal configuration file : ", config1)
    config_portal = yaml.safe_load(config1)
    text_file.close()
else:
    print()
    print ("Current time :", time.asctime())
    sys.exit("ACTION OUTPUT : portal_config.yaml file NOT present. Source APIC system does not have portal subsystem installed. Portal site restore not needed. Exiting...")

start()

print()
print ("End time :", time.asctime())