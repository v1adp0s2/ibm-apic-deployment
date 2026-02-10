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

operatornamespace = None
externalPostgresDatabase = False
externalPostgresCredentialSecret = ""

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
targetSystemSpecVersion = None
targetSystemReconciledVersion = None

pvc_name = "pvc-v2018-load"
pvc_template = {
  "apiVersion": "v1",
  "kind": "PersistentVolumeClaim",
  "metadata": {
    "name": "SOME_NAME"
  },
  "spec": {
    "accessModes": [
      "ReadWriteOnce"
    ],
    "resources": {
      "requests": {
        "storage": "10Gi"
      }
    },
    "storageClassName": "STORAGE_CLASS"
  }
}

load_job_name = "v2018-mgmt-load"
load_job_yaml = {
  "apiVersion": "batch/v1",
  "kind": "Job",
  "metadata": {
    "name": load_job_name
  },
  "spec": {
    "backoffLimit": 6,
    "completions": 1,
    "parallelism": 1,
    "template": {
      "metadata": {
        "name": load_job_name
      },
      "spec": {
        "imagePullSecrets": [
            {
                "name": "REGISTRY_SECRET"
            }
        ],
        "containers": [
          {
            "name": load_job_name,
            "image": "docker-na.artifactory.swg-devops.com/apic-dev-docker-local/ibm-apiconnect-management-v10-upgrade@sha256:4d96af476717dd0b1c6a5bc06c3587b59b658c78952fc611f1e4f6d75509ec2d",
            "imagePullPolicy": "IfNotPresent",
            "resources": {
              "limits": {
                "cpu": "8",
                "memory": "10G"
              },
              "requests": {
                "cpu": "1",
                "memory": "512Mi"
              }
            },
            "securityContext": {
              "allowPrivilegeEscalation": False,
              "runAsUser": 0
            },
            "env": [
              {
                "name": "DEBUG",
                "value": "v10-upgrade:*"
              },
              {
                "name": "LOG_DIRECTORY",
                "value": "/upgrade"
              },
              {
                "name": "NODE_OPTIONS",
                "value": "--max-old-space-size=4096"
              },
              {
                "name": "VELOX_APPLIANCE",
                "value": "true"
              },
              {
                "name": "VELOX_CERTS",
                "value": "/etc/velox/certs"
              },
              {
                "name": "VELOX_DB_MTLS",
                "value": "true"
              },
              {
                "name": "WORKING_DIRECTORY",
                "value": "/upgrade"
              },
              {
                "name": "SLEEP_BEFORE_FOR_SECONDS",
                "value": "300"
              }
            ],
            "volumeMounts": [
              {
                "mountPath": "/upgrade",
                "name": "v2018-load-volume"
              },
              {
                "mountPath": "/etc/db/postgres/creds",
                "name": "mgmt-postgres-postgres-secret",
                "readOnly": True
              },
              {
                "mountPath": "/etc/db/postgres/certs",
                "name": "mgmt-db-client-postgres",
                "readOnly": True
              },
              {
                "mountPath": "/etc/velox/certs",
                "name": "management-encryption-secret",
                "readOnly": True
              }
            ]
          }
        ],
        "restartPolicy": "OnFailure",
        "volumes": [
          {
            "name": "v2018-load-volume",
            "persistentVolumeClaim": {
              "claimName": pvc_name
            }
          },
          {
            "name": "mgmt-postgres-postgres-secret",
            "secret": {
              "defaultMode": 420,
              "secretName": "mgmt-postgres-postgres-secret"
            }
          },
          {
            "name": "mgmt-db-client-postgres",
            "secret": {
              "defaultMode": 420,
              "secretName": "mgmt-db-client-postgres"
            }
          },
          {
            "name": "management-encryption-secret",
            "secret": {
              "defaultMode": 420,
              "secretName": "mgmt-encryption-secret"
            }
          }
        ]
      }
    }
  }
}

uploadUsingNginxImage = False
deploy_name = "v2018-mgmt-upload-csv"
deploy_yaml = {
  "apiVersion": "apps/v1",
  "kind": "Deployment",
  "metadata": {
    "name": deploy_name
  },
  "spec": {
    "selector": {
      "matchLabels": {
        "app": "nginx"
      }
    },
    "replicas": 1,
    "template": {
      "metadata": {
        "labels": {
          "app": "nginx"
        }
      },
      "spec": {
        "imagePullSecrets": [
            {
                "name": "REGISTRY_SECRET"
            }
        ],
        "containers": [
          {
            "name": "nginx",
            "image": "nginx",
            "securityContext": {
              "allowPrivilegeEscalation": False,
              "runAsUser": 0
            },
            "ports": [
              {
                "containerPort": 80
              }
            ],
            "volumeMounts": [
              {
                "mountPath": "/upgrade",
                "name": "v2018-load-volume"
              }
            ]
          }
        ],
        "volumes": [
          {
            "name": "v2018-load-volume",
            "persistentVolumeClaim": {
              "claimName": pvc_name
            }
          }
        ]
      }
    }
  }
}

mgmtDetailsFromv10_ForLoadJobFileName = "mgmtDetailsFromv10_ForLoadJob.yaml"
mgmtDetailsFromv10_ForLoadJob = {
  "dbServiceHost": None,
  "dbServicePort": None,
  "encryptionSecretName": None,
  "dbClientPostgresSecretName": None,
  "postgresPostgresSecretName": None
}

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
                time.sleep(30)
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


def loadManagementData():
    global selectedMgmtSubsystemName
    global externalPostgresDatabase
    print ("Load v2018 management data into v10 ::::")
    
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

    if sourceSystemReconciledVersion.startswith("2018.") == False:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Source APIC system is not v2018 version. Version of source system is {}  Exiting...".format(sourceSystemReconciledVersion))


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
    
    # is external db for management susbsytem
    apicOpDeployYaml = runKubernetesCommand("get deploy ibm-apiconnect -o yaml", operatornamespace, True)
    apicOpDeployYaml = yaml.safe_load(apicOpDeployYaml)
    apicOPContainer = apicOpDeployYaml["spec"]["template"]["spec"]["containers"][0]
    for each in apicOPContainer["env"]:
        if each["name"] == "EXTERNAL_POSTGRES_DB" and each["value"] == "true":
            externalPostgresDatabase = True
            break
    print ("ACTION OUTPUT : External postgres database : ", externalPostgresDatabase)

    createPVCAndRunLoadJob()

    #scale apic operator to 1 replica
    scaleAPICOperator(1)

    print ("Finally scale up management micro services if they are down")
    scaleManagementServicesAccessingPostgres(False)
    time.sleep(60)

    print()
    print()
    print("Waiting for management subsystem to be healthy...    ")
    out = runKubernetesCommand("get mgmt", args.mgmt_ns, True)
    mgmtSubsystemNameInTarget = out.splitlines()[1]
    mgmtSubsystemNameInTarget = mgmtSubsystemNameInTarget[0:mgmtSubsystemNameInTarget.index(" ")]
    flag = True
    loopCount = 0
    timeout = False
    while flag:
        loopCount = loopCount + 1
        if loopCount >= 60:
            flag = False
            timeout = True
            print ("Timeout after Waiting 20 minutes for management subsytem to be healthy.")
            break # safe break after 30 minutes
        print ("Waiting for management subsystem to be healthy. Current time : ", time.asctime())
        time.sleep(30)
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



def createPVCAndRunLoadJob():
    global mgmtDetailsFromv10_ForLoadJob
    #check if load job exists and delete it
    loadJob = runKubernetesCommand("get job " + load_job_name + " --no-headers", args.mgmt_ns, False, 0, False)
    if loadJob != None and loadJob.lower().startswith(load_job_name) == True:
        runKubernetesCommand("delete job " + load_job_name, args.mgmt_ns, False)
        time.sleep(30)
    else:
        print ("ACTION OUTPUT : " + load_job_name + " job not found. Will create new load job")
    
    print ()
    #check if deployment for uploading csv into pvc exists and delete it
    downloadCSVDeploy = runKubernetesCommand("get deploy " + deploy_name + " --no-headers", args.mgmt_ns, False, 0, False)
    if downloadCSVDeploy != None and downloadCSVDeploy.lower().startswith(deploy_name):
        runKubernetesCommand("delete deploy " + deploy_name, args.mgmt_ns, False)
        time.sleep(30)
    else:
        print ("ACTION OUTPUT : " + deploy_name + " used to upload csv to pvc not found. Will create one and upload csv if needed")

    print ()
    pvc = runKubernetesCommand("get pvc " + pvc_name + " --no-headers", args.mgmt_ns, False, 0, False)
    if pvc != None and pvc.lower().startswith(pvc_name):
        runKubernetesCommand("delete pvc " + pvc_name, args.mgmt_ns, False)
        time.sleep(30)
    else:
        print ("ACTION OUTPUT : " + pvc_name + " pvc not found. Will create new pvc")

    print ()
    #create pvc
    pvc_template["metadata"]["name"] = pvc_name
    pvc_template["spec"]["storageClassName"] = args.storage_class
    if args.load_storage_size != None: 
        pvc_template["spec"]["resources"]["requests"]["storage"] = args.load_storage_size + "Gi"
    #pvc_template["spec"]["volumeName"] = selectedAvaialblePV
    with open(DATA_TEMP_DIR + "/pvc_load.yaml", 'w') as pvcFile:
        yaml.dump(pvc_template, pvcFile, default_flow_style=False)
    runKubernetesCommand("apply -f " + DATA_TEMP_DIR + "/pvc_load.yaml", args.mgmt_ns)
    time.sleep(30)

    print ()
    if args.manually_upload_extracted_data:
        print ()
        print ()
        print ("manually_upload_extracted_data flag is set.")
        print ("ACTION OUTPUT ::")
        print ("The extracted v2018 data need to be manually uploaded into the PVC with name : ", pvc_name)
        print ("The extracted contents are present in path : ", DATA_DIR + "/" + selectedMgmtSubsystemName + "/extracted_data")
        print ("Attach the pvc with name {} to a pod using mount path /upgrade and upload the contents to /upgrade directory. PVC name : ".format(pvc_name))
        print ()
        print ("Directory structure after upload to the pvc, check it :: ")
        print ("apim database csv contents in /upgrade/data/apim")
        print ("lur database csv contents in  /upgrade/data/lur")
        print ("Log info present in /upgrade/logs")
        print ()
        print ("If extracted_data not uploaded correctly, loading data into v10 will fail.")
        confirm = input("Read the above ACTION OUTPUT and upload the contents(data and log directories) of extracted_data into /upgrade directory in the pvc/pod. Once uploaded type yes here to continue : ")
        print ("Confirm upload status : ", confirm)
        if confirm != None: confirm = confirm.strip()
        confirm = confirm.lower()
        if (confirm != "yes"):
            print ("Time when error occurred :", time.asctime())
            sys.exit("ERROR : extracted_data contents not uploaded into pvc(/upgrade directory). Exiting...")
        print ()
        print ()
    else:
        if uploadUsingNginxImage:
            #upload the extracted csv and copy to data folder
            if args.nginx_image != None:
                deploy_yaml["spec"]["template"]["spec"]["containers"][0]["image"] = args.nginx_image
                if args.registry_secret == None:
                    del deploy_yaml["spec"]["template"]["spec"]["imagePullSecrets"]
                else:
                    deploy_yaml["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"] = args.registry_secret
            else:
                del deploy_yaml["spec"]["template"]["spec"]["imagePullSecrets"]

            loadCSVUploadDeploy = DATA_TEMP_DIR + "/load_csv_upload_deploy.yaml"
            with open(loadCSVUploadDeploy, 'w') as f3:
                yaml.dump(deploy_yaml, f3, default_flow_style=False)
            runKubernetesCommand("apply -f " + loadCSVUploadDeploy, args.mgmt_ns)
            time.sleep(40)
            uploadData(deploy_name)
            runKubernetesCommand("delete -f " + loadCSVUploadDeploy, args.mgmt_ns)


    foundMgmtDetailsFromv10 = False
    mgmtDetailsFromv10FileName = DATA_DIR + "/" + selectedMgmtSubsystemName + "/" + mgmtDetailsFromv10_ForLoadJobFileName
    if os.path.exists(mgmtDetailsFromv10FileName):
        print ("ACTION OUTPUT :  Found mgmtDetailsFromv10_ForLoadJob. Loading it")
        print()
        text_file = open(mgmtDetailsFromv10FileName, "r")
        config1 = text_file.read()
        print("mgmtDetailsFromv10_ForLoadJob file : ", config1)
        mgmtDetailsFromv10_ForLoadJob = yaml.safe_load(config1)
        text_file.close()
        foundMgmtDetailsFromv10 = True

    if foundMgmtDetailsFromv10 == False:
        print ()
        print ("Initially scale up apic operator if it is down")
        scaleAPICOperator(1)

        print ()
        
        print ()
        print ("Initially scale up management micro services if they are down")
        scaleManagementServicesAccessingPostgres(False)
        time.sleep(60)

        print ()
        #get inputs needed for load job
        apimDeploy = None
        apimDeploy = runKubernetesCommand("get deploy |grep -v director | grep apim", args.mgmt_ns, True)
        if apimDeploy != None and apimDeploy.lower().startswith("error") == False:
            apimDeploy = apimDeploy[0:apimDeploy.index(" ")]
            print ("apim deployment : ", apimDeploy)
        
        apimDeployment = runKubernetesCommand("get deploy " + apimDeploy + " -o yaml", args.mgmt_ns, True)
        apimDeployment = yaml.safe_load(apimDeployment)
        apimContainer = apimDeployment["spec"]["template"]["spec"]["containers"][0]

        for each in apimContainer["env"]:
            if each["name"] == "DB_SERVICE_HOST":
                if externalPostgresDatabase == False:
                    mgmtDetailsFromv10_ForLoadJob["dbServiceHost"] = each["value"]
                else:
                    cm = each["valueFrom"]["configMapKeyRef"]["name"]
                    cmPGHostKey = each["valueFrom"]["configMapKeyRef"]["key"]
                    cmObj = runKubernetesCommand("get configmap " + cm + " -o yaml", operatornamespace, True)
                    cmObj = yaml.safe_load(cmObj)
                    mgmtDetailsFromv10_ForLoadJob["dbServiceHost"] = cmObj["data"][cmPGHostKey]
            elif each["name"] == "DB_SERVICE_PORT":
                if externalPostgresDatabase == False:
                    mgmtDetailsFromv10_ForLoadJob["dbServicePort"] = each["value"]
                else:
                    cm = each["valueFrom"]["configMapKeyRef"]["name"]
                    cmPGPortKey = each["valueFrom"]["configMapKeyRef"]["key"]
                    cmObj = runKubernetesCommand("get configmap " + cm + " -o yaml", operatornamespace, True)
                    cmObj = yaml.safe_load(cmObj)
                    mgmtDetailsFromv10_ForLoadJob["dbServicePort"] = cmObj["data"][cmPGPortKey]


        volumeMountNameEncSecret = None
        for each in apimContainer["volumeMounts"]:
            if each["mountPath"] == "/etc/velox/certs":
                volumeMountNameEncSecret = each["name"]
                break
        print ("ACTION OUTPUT : volumeMount Name Encryption Secret : ", volumeMountNameEncSecret)

        for each in apimDeployment["spec"]["template"]["spec"]["volumes"]:
            if volumeMountNameEncSecret in each["name"]:
                mgmtDetailsFromv10_ForLoadJob["encryptionSecretName"] = each["secret"]["secretName"]
            elif each["name"].endswith("db-client-postgres"):
                mgmtDetailsFromv10_ForLoadJob["dbClientPostgresSecretName"] = each["secret"]["secretName"]
            elif each["name"].endswith("postgres-postgres-secret"):
                mgmtDetailsFromv10_ForLoadJob["postgresPostgresSecretName"] = each["secret"]["secretName"]
        
        # save mgmtDetailsFromv10_ForLoadJob 
        with open(mgmtDetailsFromv10FileName, 'w') as f4:
            yaml.dump(mgmtDetailsFromv10_ForLoadJob, f4, default_flow_style=False)


    print ("ACTION OUTPUT : DB_SERVICE_HOST : ", mgmtDetailsFromv10_ForLoadJob["dbServiceHost"])
    print ("ACTION OUTPUT : DB_SERVICE_PORT : ", mgmtDetailsFromv10_ForLoadJob["dbServicePort"])

    print ("ACTION OUTPUT : Encryption Secret name : ", mgmtDetailsFromv10_ForLoadJob["encryptionSecretName"])
    print ("ACTION OUTPUT : db-client-postgres Secret name : ", mgmtDetailsFromv10_ForLoadJob["dbClientPostgresSecretName"])
    print ("ACTION OUTPUT : postgres-postgres-secret name : ", mgmtDetailsFromv10_ForLoadJob["postgresPostgresSecretName"])
    print ()

    
    if args.registry_secret == None:
        del load_job_yaml["spec"]["template"]["spec"]["imagePullSecrets"]
    else:
        load_job_yaml["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"] = args.registry_secret
    
    db_service_host_env = {
        "name": "DB_SERVICE_HOST",
        "value": mgmtDetailsFromv10_ForLoadJob["dbServiceHost"]
    }
    db_service_port_env = {
        "name": "DB_SERVICE_PORT",
        "value": mgmtDetailsFromv10_ForLoadJob["dbServicePort"]
    }
    custom_db_ca = {
        "name": "CUSTOM_DB_CA",
        "value": "/etc/db/external_db/creds/root.crt"
    }

    load_job_yaml["spec"]["template"]["spec"]["containers"][0]["env"].append(db_service_host_env)
    if mgmtDetailsFromv10_ForLoadJob["dbServicePort"] != None:
        load_job_yaml["spec"]["template"]["spec"]["containers"][0]["env"].append(db_service_port_env)
    if externalPostgresDatabase:
        load_job_yaml["spec"]["template"]["spec"]["containers"][0]["env"].append(custom_db_ca)
        load_job_yaml["spec"]["template"]["spec"]["containers"][0]["volumeMounts"].append({
            "name" : externalPostgresCredentialSecret,
            "mountPath": "/etc/db/external_db/creds"
        })

        load_job_yaml["spec"]["template"]["spec"]["volumes"].append({
            "name": externalPostgresCredentialSecret,
            "secret": {
              "defaultMode": 420,
              "secretName": externalPostgresCredentialSecret
            }
        })
    
    if args.manually_upload_extracted_data == False and uploadUsingNginxImage == False:
        env1 = {
            "name": "FROM_FFM_WAIT_FOR_CSV_TASK_COMPLETION",
            "value": "true"
        }
        env2 = {
            "name": "FROM_FFM_CSV_TASK_LOOP_COUNT",
            "value": "60"
        }
        load_job_yaml["spec"]["template"]["spec"]["containers"][0]["env"].append(env1)
        load_job_yaml["spec"]["template"]["spec"]["containers"][0]["env"].append(env2)


    if args.load_image != None:
        load_job_yaml["spec"]["template"]["spec"]["containers"][0]["image"] = args.load_image
    
    for each in load_job_yaml["spec"]["template"]["spec"]["volumes"]:
        if "management-encryption-secret" in each["name"]:
            each["secret"]["secretName"] = mgmtDetailsFromv10_ForLoadJob["encryptionSecretName"]
        elif "db-client-postgres" in each["name"]:
            if externalPostgresDatabase:
                secretData = runKubernetesCommand("get secret " + externalPostgresCredentialSecret + " -o yaml", args.mgmt_ns)
                secretData = yaml.safe_load(secretData)
                root_crt = secretData["data"]["root.crt"]
                secretData = runKubernetesCommand("get secret " + mgmtDetailsFromv10_ForLoadJob["dbClientPostgresSecretName"] + " -o yaml", args.mgmt_ns)
                secretData = yaml.safe_load(secretData)
                if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                if "labels" in secretData["metadata"]: del secretData["metadata"]["labels"]
                if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                name = secretData["metadata"]["name"] + "-custom-ffm"
                secretData["metadata"]["name"] = name
                secretData["data"]["ca.crt"] = root_crt
                with open(DATA_TEMP_DIR + "/" + name + ".yaml", 'w') as sfile:
                    yaml.dump(secretData, sfile, default_flow_style=False)
                runKubernetesCommand("apply -f " + DATA_TEMP_DIR + "/" + name + ".yaml", args.mgmt_ns)

                each["secret"]["secretName"] = name
            else:
                each["secret"]["secretName"] = mgmtDetailsFromv10_ForLoadJob["dbClientPostgresSecretName"]
        elif "postgres-postgres-secret" in each["name"]:
            each["secret"]["secretName"] = mgmtDetailsFromv10_ForLoadJob["postgresPostgresSecretName"]
    
    with open(DATA_TEMP_DIR + "/load_job.yaml", 'w') as f3:
        yaml.dump(load_job_yaml, f3, default_flow_style=False)

    if externalPostgresDatabase:
        print ("ACTION OUTPUT : Calling reset portal as this is RI stack")
        loginAndResetPortal()

    print ()
    print ("Scale down management micro services before starting load job")
    scaleManagementServicesAccessingPostgres(True)
    print ()
    scaleAPICOperator(0)
    time.sleep(30)

    #start load job
    print ("Starting load job")
    runKubernetesCommand("apply -f " + DATA_TEMP_DIR + "/load_job.yaml", args.mgmt_ns)
    time.sleep(120)

    if args.manually_upload_extracted_data == False and uploadUsingNginxImage == False:
        neededPod = uploadData(load_job_name)
        file_name = DATA_TEMP_DIR + "/csvUploadComplete.txt"
        f = open(file_name, 'a')  # open file in write mode
        f.write('csv upload complete')
        f.close()
        runKubernetesCommand("cp " + file_name + " " + args.mgmt_ns + "/" + neededPod + ":/upgrade/logs/csvUploadComplete.txt", None, False, 50, True)
        time.sleep(30)


    while isLoadJobCompleted() == False:
        print ("Waiting for load job({}) to be completed.".format(load_job_name))
        time.sleep(120)

    loadJob = runKubernetesCommand("get job " + load_job_name + " -o yaml", args.mgmt_ns, True, 15, False)
    loadJob = yaml.safe_load(loadJob)
    if "status" not in loadJob or "succeeded" not in loadJob["status"] or loadJob["status"]["succeeded"] != 1:
        sys.exit("ERROR : Load job failed. Could not load data into v10 management system.")
    print ("ACTION OUTPUT : Loaded v2018 management data into v10 management subsystem")


def uploadData(usingPodName):
    pods = runKubernetesCommand("get pods --no-headers", args.mgmt_ns, True)
    neededPod = None
    if pods != None and pods.lower().startswith("error") == False:
        pods = pods.splitlines()
        for eachPod in pods:
            if usingPodName in eachPod:
                neededPod = eachPod[0:eachPod.index(" ")]
                break
    print ("ACTION OUTPUT : Use this pod to upload csv into pvc : ", neededPod)

    if neededPod == None:
        sys.exit("Pod to upload csv to pvc is not ready/created. The pod name is not available. Check deployment yaml (oc get deploy " + usingPodName + " -o yaml)")
    
    if not os.path.exists(DATA_DIR + "/" + selectedMgmtSubsystemName + "/extracted_data/data"):
        sys.exit("Extracted csv data not found. Directoty, {} does not exist".format(DATA_DIR + "/" + selectedMgmtSubsystemName + "/extracted_data/data"))
    
    if not os.path.exists(DATA_DIR + "/" + selectedMgmtSubsystemName + "/extracted_data/logs"):
        sys.exit("Extracted csv data not found. Directoty, {} does not exist".format(DATA_DIR + "/" + selectedMgmtSubsystemName + "/extracted_data/logs"))

    runKubernetesCommand("cp " + DATA_DIR + "/" + selectedMgmtSubsystemName + "/extracted_data/data " + args.mgmt_ns + "/" + neededPod + ":/upgrade", None, False, 50, True)
    runKubernetesCommand("cp " + DATA_DIR + "/" + selectedMgmtSubsystemName + "/extracted_data/logs " + args.mgmt_ns + "/" + neededPod + ":/upgrade", None, False, 50, True)
    print ("ACTION OUTPUT : Uploaded csv data of v2018 management to PVC")
    time.sleep(90)
    return neededPod


def isLoadJobCompleted():
    loadJob = runKubernetesCommand("get job " + load_job_name + " --no-headers", args.mgmt_ns, False, 15, False)
    if loadJob != None and loadJob.lower().startswith(load_job_name):
        loadJob = runKubernetesCommand("get job " + load_job_name + " -o yaml", args.mgmt_ns, True, 15, False)
        loadJob = yaml.safe_load(loadJob)
        if "conditions" in loadJob["status"]:
            for eachCondition in loadJob["status"]["conditions"]:
                if (eachCondition["type"] == "Complete" and eachCondition["status"] == "True"):
                    return True
    else:
        sys.exit("Load job not found. Exiting.")
    return False


mgmtServices = ["apim", "apim-schema", "apim-data-populate", "lur", "lur-schema", "lur-data", "taskmanager", "portal-proxy", "analytics-proxy", "websocket-proxy", "juhu", "billing", "-ui-"]
mgmtServices2 = ["apim", "lur", "taskmanager", "portal-proxy", "analytics-proxy", "websocket-proxy", "juhu", "-ui-"]
def scaleManagementServicesAccessingPostgres(scaleDown=True):
    global externalPostgresCredentialSecret
    if scaleDown == False:
        scalePostgresPGBouncer(scaleDown)
    
    print ("Scaling management services accessing postgres database. scale down : {}  and timestamp : {}".format(scaleDown, time.asctime()))
    cr = runKubernetesCommand("get apiconnectcluster --no-headers", args.mgmt_ns, True, 1, False)
    resourceType = "apiconnectcluster"

    crName = None
    if cr != None and cr.lower().startswith("error") == False:
        resourceType = "mgmt"
        cr = runKubernetesCommand("get mgmt --no-headers", args.mgmt_ns)

    cr = cr.splitlines()[0]
    crName = cr[0:cr.index(" ")]
    
    cr = runKubernetesCommand("get " + resourceType + " " + crName + " -o yaml", args.mgmt_ns, True)
    cr = yaml.safe_load(cr)

    if "externalDB" in cr["spec"]:
        externalPostgresCredentialSecret = cr["spec"]["externalDB"]["credentialSecret"]
        print ("ACTION OUTPUT : externalPostgresCredentialSecret : ", externalPostgresCredentialSecret)

    # first time only
    if os.path.exists(DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load0.yaml") == False:

        confirm = input(" Confirm that management subsystem is healthy and all pods are running (type yes if management is healthy) : ")
        print ("Confirm upload status : ", confirm)
        if confirm != None: confirm = confirm.strip()
        confirm = confirm.lower()
        if (confirm != "yes"):
            print ("Time when failed :", time.asctime())
            sys.exit("ERROR : Management susbystem not healthy. Bring up management to healthy state with all pods running and try again.")

        print ("Saving the CR first time to handle templates if present")
        with open(DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load0.yaml", 'w') as configFile:
            yaml.dump(cr, configFile, default_flow_style=False)

        if "creationTimestamp" in cr["metadata"]: del cr["metadata"]["creationTimestamp"]
        if "uid" in cr["metadata"]: del cr["metadata"]["uid"]
        if "resourceVersion" in cr["metadata"]: del cr["metadata"]["resourceVersion"]
        if "status" in cr: del cr["status"]
        if "annotations" in cr: del cr["annotations"]
        if "generation" in cr: del cr["generation"]

        #this yaml is applied after data is loaded so that the original template if available will be appied
        with open(DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load1.yaml", 'w') as configFile:
            yaml.dump(cr, configFile, default_flow_style=False)

        # for top cr?
        if "billing" in cr["spec"]:
            cr["spec"]["billing"]["enabled"] = False

        if "template" in cr["spec"]:
            requiredMicroServicesInTemplate = []
            for e1 in cr["spec"]["template"]:
                if e1["name"] in mgmtServices:
                    requiredMicroServicesInTemplate.append(e1["name"])
            print ("requiredMicroServicesInTemplate : ", requiredMicroServicesInTemplate)

            for e2 in mgmtServices:
                if e2 in requiredMicroServicesInTemplate:
                    for each in cr["spec"]["template"]:
                        if each["name"] == e2:
                            each["enabled"] = False
                else:
                    cr["spec"]["template"].append({"name": e2, "enabled": False})
            
            #this yaml is applied to bring the micro services accessing postgres down
            with open(DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load2.yaml", 'w') as configFile:
                yaml.dump(cr, configFile, default_flow_style=False)


    if scaleDown:
        if os.path.exists(DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load2.yaml") == True:
            runKubernetesCommand("apply -f " + DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load2.yaml", args.mgmt_ns)
            #runKubernetesCommand('patch ' + resourceType + ' ' + crName + ' --type="json" --patch="[{\\"op\\": \\"replace\\", \\"path\\": \\"/spec/template\\", \\"value\\": [{\\"enabled\\": false, \\"name\\":\\"apim\\"}, {\\"enabled\\": false, \\"name\\":\\"apim-schema\\"}, {\\"enabled\\": false, \\"name\\":\\"apim-data\\"}, {\\"enabled\\": false, \\"name\\":\\"lur\\"}, {\\"enabled\\": false, \\"name\\":\\"lur-schema\\"}, {\\"enabled\\": false, \\"name\\":\\"lur-data\\"}, {\\"enabled\\": false, \\"name\\":\\"taskmanager\\"}, {\\"enabled\\": false, \\"name\\":\\"analytics-proxy\\"}, {\\"enabled\\": false, \\"name\\":\\"portal-proxy\\"}, {\\"enabled\\": false, \\"name\\":\\"juhu\\"}, {\\"enabled\\": false, \\"name\\":\\"websocket-proxy\\"}, {\\"enabled\\": false, \\"name\\":\\"ui\\"}, {\\"enabled\\": false, \\"name\\":\\"billing\\"}]}]"', args.mgmt_ns, False)
        else:
            if "template" not in cr["spec"]:
                runKubernetesCommand('patch ' + resourceType + ' ' + crName + ' --type="json" --patch="[{\\"op\\": \\"add\\", \\"path\\": \\"/spec/template\\", \\"value\\": [{\\"enabled\\": false, \\"name\\":\\"apim\\"}, {\\"enabled\\": false, \\"name\\":\\"apim-schema\\"}, {\\"enabled\\": false, \\"name\\":\\"apim-data\\"}, {\\"enabled\\": false, \\"name\\":\\"lur\\"}, {\\"enabled\\": false, \\"name\\":\\"lur-schema\\"}, {\\"enabled\\": false, \\"name\\":\\"lur-data\\"}, {\\"enabled\\": false, \\"name\\":\\"taskmanager\\"}, {\\"enabled\\": false, \\"name\\":\\"analytics-proxy\\"}, {\\"enabled\\": false, \\"name\\":\\"portal-proxy\\"}, {\\"enabled\\": false, \\"name\\":\\"juhu\\"}, {\\"enabled\\": false, \\"name\\":\\"websocket-proxy\\"}, {\\"enabled\\": false, \\"name\\":\\"ui\\"}, {\\"enabled\\": false, \\"name\\":\\"billing\\"}]}]"', args.mgmt_ns, False)
            else:
                print("template already present. move forward")    
    else:
        if "template" in cr["spec"]:
            if os.path.exists(DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load1.yaml"):
                file3 = open(DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load1.yaml", "r")
                c = file3.read()
                savedCR = yaml.safe_load(c)
                text_file.close()
                if "template" in savedCR["spec"]:
                    useCustomImageForApimASchema = False
                    if useCustomImageForApimASchema and externalPostgresDatabase: # hardcode ri stack, remove later https://github.ibm.com/velox/platform/issues/7479
                        savedCR["spec"]["template"].append({
                            "name": "apim-schema",
                            "containers": [{
                                "image": "docker-na.artifactory.swg-devops.com/apic-dev-docker-local/ibm-apiconnect-management-apim@sha256:2c2600334f9f711596401eb23d4eb1db5e4356afdbe975b9d355428220f476d8",
                                "name": "apim-schema"
                            }]
                        })
                        with open(DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load1_custom_image.yaml", 'w') as cf5:
                            yaml.dump(savedCR, cf5, default_flow_style=False)
                        runKubernetesCommand("apply -f " + DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load1_custom_image.yaml", args.mgmt_ns)
                    else:
                        runKubernetesCommand("apply -f " + DATA_DIR + "/" + selectedMgmtSubsystemName + "/cr_during_load1.yaml", args.mgmt_ns)
                else:
                    runKubernetesCommand('patch ' + resourceType + ' ' + crName + ' --type="json" --patch="[{\\"op\\": \\"remove\\", \\"path\\": \\"/spec/template\\" }]"', args.mgmt_ns, False)

    while True:
        flag = False
        podsOutput = runKubernetesCommand("get pods --no-headers | grep -v director | grep Running", args.mgmt_ns, False)
        if podsOutput != None and podsOutput.lower().startswith("error") == False:
            if scaleDown:
                for eachService in mgmtServices:
                    if eachService in podsOutput:
                        print ("{} present in pods output".format(eachService))
                        flag = True
                        break
            else:
                for eachService in mgmtServices2:
                    if eachService not in podsOutput:
                        print ("{} NOT present in pods output".format(eachService))
                        flag = True
                        break
            if flag:
                print ("Sleeping for 120 seconds for the management services accessing postgres to scale..", time.asctime())
                time.sleep(120)
            else:
                break
    print ("ACTION OUTPUT : Management services that access postgres database are scaled.", time.asctime())
    
    if scaleDown:
        scalePostgresPGBouncer(scaleDown)


def scalePostgresPGBouncer(scaleDown=True):
    print ("Scaling postgres pgbouncer")
    #postgres pgbouncer scale
    deployments = runKubernetesCommand("get deployment", args.mgmt_ns)
    deploymentList = deployments.splitlines()
    for eachDeploy in deploymentList:
        if "pgbouncer" in eachDeploy:
            pgBouncerDeploymentName = eachDeploy[0:eachDeploy.index(" ")]
            if scaleDown:
                runKubernetesCommand('patch deploy ' + pgBouncerDeploymentName + ' --type="json" --patch="[{\\"op\\": \\"replace\\", \\"path\\": \\"/spec/replicas\\", \\"value\\": 0}]"', args.mgmt_ns)
            else:
                runKubernetesCommand('patch deploy ' + pgBouncerDeploymentName + ' --type="json" --patch="[{\\"op\\": \\"replace\\", \\"path\\": \\"/spec/replicas\\", \\"value\\": 1}]"', args.mgmt_ns)
            break
    time.sleep(45)


def scaleAPICOperator(replicas=0):
    print ("Scaling({}) APIC operator. timestmap : {} ".format(replicas, time.asctime()))
    
    isCSV = False
    apicCSV = runKubernetesCommand("get csv | grep ibm-apiconnect", operatornamespace, True, 1, False)

    print ("output : ", apicCSV)
    if apicCSV != None and apicCSV.lower().startswith("error") == False and apicCSV.lower().startswith("no resources found") == False:
        print ("apic operator csv.")
        isCSV = True
    else:
        print ("apic operator deployment.")
        apicCSV = runKubernetesCommand("get deploy | grep ibm-apiconnect", operatornamespace)

    apicCSVName = apicCSV[0:apicCSV.index(" ")]
    print ("Scaling apic operator csv/deployment {} in namespace {}".format(apicCSVName, operatornamespace))

    if replicas == 0:
        if isCSV:
            runKubernetesCommand('patch csv ' + apicCSVName + ' --type="json" --patch="[{\\"op\\": \\"replace\\", \\"path\\": \\"/spec/install/spec/deployments/0/spec/replicas\\", \\"value\\": 0}]"', operatornamespace)
        else:
            runKubernetesCommand('patch deploy ' + apicCSVName + ' --type="json" --patch="[{\\"op\\": \\"replace\\", \\"path\\": \\"/spec/replicas\\", \\"value\\": 0}]"', operatornamespace)
        
        while True:
            podsOutput = runKubernetesCommand("get pods --no-headers | grep Running", operatornamespace, False)
            if podsOutput != None and podsOutput.lower().startswith("error") == False:
                if "ibm-apiconnect-" in podsOutput:
                    print ("api connect operator present in pods output. Sleeping for 120 seconds..", time.asctime())
                    time.sleep(120)
                else:
                    break
    elif replicas == 1:
        if isCSV:
            runKubernetesCommand('patch csv ' + apicCSVName + ' --type="json" --patch="[{\\"op\\": \\"replace\\", \\"path\\": \\"/spec/install/spec/deployments/0/spec/replicas\\", \\"value\\": 1}]"', operatornamespace)
        else:
            runKubernetesCommand('patch deploy ' + apicCSVName + ' --type="json" --patch="[{\\"op\\": \\"replace\\", \\"path\\": \\"/spec/replicas\\", \\"value\\": 1}]"', operatornamespace)

        while True:
            podsOutput = runKubernetesCommand("get pods --no-headers | grep Running", operatornamespace, False)
            if podsOutput != None and podsOutput.lower().startswith("error") == False:
                if "ibm-apiconnect-" not in podsOutput:
                    print ("api connect operator not present in pods output. Sleeping for 120 seconds..", time.asctime())
                    time.sleep(120)
                else:
                    break
    else:
        sys.exit("Invalid replicas ({}) value provided for scaloing api connec operator.".format(replicas))

    print ("ACTION OUTPUT : Scaled apic operator.", time.asctime())

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
    
    if isCP4I or externalPostgresDatabase:
        out1 = runKubernetesCommand("get apiconnectcluster.apiconnect.ibm.com --no-headers", args.mgmt_ns, True, 1, False)
        if (out1 != None and out1 != "") or externalPostgresDatabase:
            if externalPostgresDatabase:
                #just to read mgmt-admin-pass secret
                topCRName = "apic"
            else:
                out1 = out1.strip()
                topCRName = out1[0:out1.index(" ")]
                print("top cr name : ", topCRName)

            if args.password == None or args.password  == "":
                adminSecret = runKubernetesCommand("get secret " + topCRName + "-mgmt-admin-pass -o yaml", args.mgmt_ns, False)
                adminSecret = yaml.safe_load(adminSecret)

                #saving to track the original value
                adminPassSecretFilename = DATA_TEMP_DIR + "/" + topCRName + "-mgmt-admin-pass_step4.yaml"
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
                runKubernetesCommand('patch secret ' + topCRName + '-mgmt-admin-pass --patch="{\\"data\\":{\\"password\\":\\"'+encodedPassword+'\\"}}"', args.mgmt_ns, False)
                print("ACTION OUTPUT : Updated secret(" + topCRName + "-mgmt-admin-pass) with cloud manager password after restoring database.")
    else:
        adminPassword = args.password


    if args.server == None:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Exiting. This is either RI stack or CP4I instance or -reset_gateway_portal flag ise set. Hostname to connect to cloud manager (provide hostname of platform API) is NOT provided. Need this to factory reset portal subsystem. Use flag --server or -s to provide the hostname and try again.")
    
    if adminPassword == None:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Exiting. This is either RI stack or CP4I instance or -reset_gateway_portal flag ise set. admin password is needed to connect to cloud manager. Need this to factory reset portal subsystem. Use flag --password or -p to provide the password and try again.")

    print (adminPassword)
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

    print("Loading management data of source system")
    loadManagementData()
    
    if isCP4I: 
        checkAndApplyCP4ICredsSecret()

    if isCP4I or args.reset_gateway_portal or externalPostgresDatabase:
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
parser.add_argument("-p", "--password", dest = "password", help="password to connect to cloud manager using admin user. This is needed to need to factory reset portal subsystems when Kubernetes is the target cluster.")
parser.add_argument('-reset_gateway_portal', "--reset_gateway_portal", action='store_true', dest = "reset_gateway_portal", help='Restart gateway pods and factory reset portal subsystems.')

parser.add_argument('-ignore_health_check', "--ignore_health_check", action='store_true', dest = "ignore_health_check", help='ignores health check status for each subsystem and proceeds.')

parser.add_argument('-skip_namespace_validation', "--skip_namespace_validation",  action='store_true', dest = "skip_namespace_validation", help='Skips validation of input namespaces.')

parser.add_argument('-silent', "--silent", action='store_true', dest = "silent", help='Does not prompt for additinal inputs and proceeds silently.')
parser.add_argument('-mgmt_subsys_name', "--mgmt_subsystem_name", dest = "mgmt_subsystem_name", help='If multiple management subsytems present in the configuration, the script will use this.')
parser.add_argument("-cp4i", "--cp4i",  action='store_true', dest = "cp4i", help="It is Cloud Pak for Integration cluster.")

parser.add_argument("-storage_class", "--storage_class", dest = "storage_class", help="Storage class used by the upgrade PVC.")
parser.add_argument("-registry_secret", "--registry_secret", dest = "registry_secret", help="Registry secret of the registry where the v2018 extract docker image is present. This is optional and need to be given if required for the download of the image.")
parser.add_argument("-load_image", "--load_image", dest = "load_image", help="The image value used to run load pod which loads v2018 management data into v10 postgres. This is optional and used to override default value.")
parser.add_argument("-nginx_image", "--nginx_image", dest = "nginx_image", help="temporarily use this to download the csv files.")
parser.add_argument("-load_storage_size", "--load_storage_size", dest = "load_storage_size", help="The storage request size used by the pvc in load pod. Default is 10 GB. You need to give the value as a number 10 or 20 etc.")

parser.add_argument("-operator_namespace", "--operator_namespace", dest = "operator_namespace", help="Namespace where apic operator is installed.")

parser.add_argument('-manually_upload_extracted_data', "--manually_upload_extracted_data", action='store_true', dest = "manually_upload_extracted_data", help='If this flag is used, the program waits on a prompt for you to manually upload the csv and once you confirm that v2018 extracted data is uploaded, it moves forward.')

args = parser.parse_args()

print ("Start time :", time.asctime())
print ()

print ("Input namespace provided for all subsystems (-n or --namespace flag) : ", args.ns)
print ("Input namespace provided for management subsystem (-mgmt_ns or --management_namespace flag) : ", args.mgmt_ns)
print ("Input namespace where additional gateway subsystem are installed(-gw_ns or --gw_ns flag) : ", args.gw_ns)
print ()

print ("hostname to connect to cloud manager(-s or --server flag) : ", args.server)
print ()

print ("Reset gateway portal flag : (-reset_gateway_portal or --reset_gateway_portal flag) : ", args.reset_gateway_portal)
print ("Ignore health check status for each subsystem (-ignore_health_check or --ignore_health_check flag) : ", args.ignore_health_check)
print ()

print ("Storage class used to create the pvc used by extract job (-storage_class or --storage_class flag) : ", args.storage_class)
print ("Load image value. The load image will be downloaded from this location (-load_image or --load_image flag) : ", args.load_image)
print ("Registry secret used to download extract image from the registry. This is optional. (-registry_secret or --registry_secret flag) : ", args.registry_secret)
print ("Load PVC storage size (-load_storage_size or --load_storage_size flag) : ", args.load_storage_size)
print ("image used to upload csv to pvc needed for load job (-nginx_image or --nginx_image flag) : ", args.nginx_image)
print ()

print ("silent (-silent or --silent flag) : ", args.silent)
print ("Mangement subsystem name (-mgmt_subsys_name or --mgmt_subsystem_name flag) : ", args.mgmt_subsystem_name)
print ("is CP4I installation (-cp4i or --cp4i flag) : ", args.cp4i)

print ("Namespace where operator is installed (-operator_namespace or --operator_namespace flag) : ", args.operator_namespace)
print ("Manually upload v2018 extracted data (-manually_upload_extracted_data or --manually_upload_extracted_data flag) : ", args.manually_upload_extracted_data)
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

if args.storage_class == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Storage class used by the upgrade pvc cannot be null. Use flag -storage_class or --storage_class to provide the storage class. Exiting...")

if args.load_image == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Need to provide load image used to load the extracted csv into v10. Use flag -load_image or --load_image. Exiting...")


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

if args.operator_namespace:
    operatornamespace = args.operator_namespace
else:    
    operatornamespace = args.mgmt_ns

start();

print()
print ("End time :", time.asctime())