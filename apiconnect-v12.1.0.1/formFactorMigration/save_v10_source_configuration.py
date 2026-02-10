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
import random
import shutil
import yaml
import base64

subsystems = ("mgmt", "ptl", "gw", "a7s")
ns = []


oc_client = "oc"
kubectl_client = "kubectl"
client = oc_client

pwd = None
DATA_DIR = None
DATA_TEMP_DIR = None

CONFIG_FILE_NAME = "config.yaml"
CONFIG_PORTAL_FILE_NAME = "config_portal.yaml"
mgmtSubsystemName = None
portalSubsystemName = None
cloudAdminServer = None
forceLogPasswords = None

config =  {
	"management_subsystem": {
	},
	"analytics_subsystem": {
	},
	"gateway_subsystem": {
	}
}

config_portal = {
	"portal_subsystem": {
	}
}

mgmt_backup = {
  "apiVersion": "management.apiconnect.ibm.com/v1beta1",
  "kind": "ManagementBackup",
  "metadata": {
    "generateName": "management-"
  },
  "spec" : {
    "type": "full",
    "crType": "create",
    "clusterName": "management"
  }
} 

mgmt_edb_backup = {
  "apiVersion": "postgresql.k8s.enterprisedb.io/v1",
  "kind": "Backup",
  "metadata": {
    "name": "management-backup1"
  },
  "spec" : {
    "cluster": {
      "name": "TBD"
    }
  }
}

ptl_backup = {
  "apiVersion": "portal.apiconnect.ibm.com/v1beta1",
  "kind": "PortalBackup",
  "metadata": {
    "generateName": "portal-bup-"
  },
  "spec" : {
    "type": "all",
    "portalCluster": "portal",
    "crType": "create",
    "comment": "test comment"
  }
} 

gateway_portal_mapping_filename = "gateway_portal_mapping.yaml"
gateway_portal_mapping = {
    "gateway_mapping":{},
    "portal_mapping":{},
    "analytics_mapping":{}
}

provider_org_credentials_filename = "provider_org_credentials.yaml"
porg_credentials = {
    "provider_org_credentials" :{
        "apiManagerHostName": "PLATFORM_API_HOSTNAME",
        "useSameCredentialsForAllProviderOrgs": False
    }
}

managementSecrets = ["encryptionSecret", "atmCredentialSecret", "consumerToolkitCredentialSecret", "consumerUICredentialSecret", "designerCredentialSecret", 
"juhuCredentialSecret", "toolkitCredentialSecret", "uiCredentialSecret"]
portalSecrets = ["encryptionSecret"]

apic_resources = {
  "cloud-settings": {
    "methods": ["get"]
  },
  "user-registry-settings": {
    "methods": ["get"]
  },
  "orgs": {
    "field_name": "org",
    "fields_in_list_output": "id,name,org_type",
    "additional_params_for_list": "--org_type admin",
    "availability-zones": {
      "field_name": "availability-zone",
      "portal-services": {},
      "analytics-services": {},
      "gateway-services": {
        "field_name": "gateway-service",
        "gateway-extensions": {
          "additional_params_for_get": "--scope org",
          "methods": ["get", "implementation"]
        }
      }
    },
    "user-registries": {
      "field_name": "user-registry",
      "users": {}
    }
  }
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
    if ("--password" in command or "--apiKey" in command) and forceLogPasswords != "true":
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


# getSubsystemDetails
def getSubsystemDetails():
    global mgmtSubsystemName
    global portalSubsystemName
    for i in range(4):
        if subsystems[i] == "mgmt" and  (args.skip_mgmt == True or ns[i] == None):
            print ("ACTION OUTPUT : Skipping management subsystem because skip_mgmt flag is set OR management namespace is NOT provided in the input.")
            print()
            continue
        elif subsystems[i] == "ptl" and (args.skip_ptl == True or ns[i] == None):
            print ("ACTION OUTPUT : Skipping portal subsystem because skip_ptl flag is set OR portal namespace is NOT provided in the input.")
            print()
            continue
        elif subsystems[i] == "gw" and  (args.skip_gw == True or ns[i] == None):
            print ("ACTION OUTPUT : Skipping gateway subsystem because skip_gw flag is set OR gateway namespace is NOT provided in the input.")
            print()
            continue
        elif subsystems[i] == "a7s" and (args.skip_a7s == True or ns[i] == None):
            print ("ACTION OUTPUT : Skipping analytics subsystem because skip_a7s flag is set OR analytics namespace is NOT provided in the input.")
            print()
            continue
        
        subsystemName = None
        giveNNamespacesForSubsystemType = ns[i].split("|")
        for eachNamespace in giveNNamespacesForSubsystemType:
            print("Checking for {} subsystems in namespace : {}".format(subsystems[i], eachNamespace))
            out = runKubernetesCommand("get " + subsystems[i], eachNamespace)
            outList = out.splitlines()
            k = 0
            for each in outList:
                if k == 0:
                    k = k + 1
                    continue
                subsystemName = each[0:each.index(" ")]
                print(subsystems[i] + " subsystem name ::: " + subsystemName)
                crData = runKubernetesCommand("get " + subsystems[i] + " " + subsystemName + " -o yaml", eachNamespace, True)
                crData = yaml.safe_load(crData)
                
                if not os.path.exists(DATA_DIR + "/" + subsystemName ):
                    os.makedirs(DATA_DIR + "/" + subsystemName , mode=0o755, exist_ok=True)
                
                # check health
                print ("Phase : {} and state : {} for {} subsystem, {}".format(crData["status"]["phase"], crData["status"]["state"], subsystems[i], subsystemName))
                if not args.ignore_health_check:
                    state = crData["status"]["state"]
                    if crData["status"]["phase"] != "Running" or state[0:state.index("/")] != state[state.index("/") + 1:]:
                        print ("Time when error occurred :", time.asctime())
                        sys.exit("ERROR : Health check failed for {} subsystem with name {}. Phase : {} and state : {}".format(subsystems[i], subsystemName, crData["status"]["phase"], crData["status"]["state"]))
                    print ("ACTION OUTPUT : {} subsytem with name {} is healthy".format(subsystems[i], subsystemName))
                print ()
                
                
                if subsystems[i] == "mgmt":
                    if subsystemName != None:
                    
                        mgmtSubsystemName = subsystemName
                    
                        # check for backup configuration
                        if args.skip_mgmt_backup == False:
                            print ("Validating database backup configuration for management subsystem")
                            if "databaseBackup" not in crData["spec"]:
                                print ("Time when error occurred :", time.asctime())
                                sys.exit("ERROR : Management subsystem ({}) validation failed. Database backup not configured.  Exiting...".format(mgmtSubsystemName))
                            else:
                                dbBackup = crData["spec"]["databaseBackup"]
                                if "host" not in dbBackup or "path" not in dbBackup or "credentials" not in dbBackup or "protocol" not in dbBackup:
                                    print ("Time when error occurred :", time.asctime())
                                    sys.exit("ERROR : Management subsystem ({}) validation failed. Database backup not configured. Check host, credentials, path.  Exiting...".format(mgmtSubsystemName))
                                if "protocol" in dbBackup and dbBackup["protocol"] == "sftp" and "port" not in dbBackup:
                                    print ("Time when error occurred :", time.asctime())
                                    sys.exit("ERROR : Management subsystem ({}) validation failed. Database backup not configured. Check port number.  Exiting...".format(mgmtSubsystemName))
                            print ()
                    
                        for eachSecret in managementSecrets:
                            if eachSecret not in crData["status"]:
                                print ("Time when error occurred :", time.asctime())
                                sys.exit("ERROR : Secret {} not present in the management CR status for subsystem with name {}".format(eachSecret, mgmtSubsystemName))
                    
                        d1 = {}
                        if mgmtSubsystemName in config["management_subsystem"]:
                            d1 = config["management_subsystem"][mgmtSubsystemName]

                        #store in same format as CR consumes
                        d1["encryptionSecret"] = {
                            "secretName": crData["status"]["encryptionSecret"]
                        }
                        
                        #store in same format as CR consumes
                        d1["customApplicationCredentials"] = []
                        
                        d1["customApplicationCredentials"].append({
                            "name" : "atm-cred",
                            "secretName": crData["status"]["atmCredentialSecret"]
                        })
                        
                        d1["customApplicationCredentials"].append({
                            "name" : "ccli-cred",
                            "secretName": crData["status"]["consumerToolkitCredentialSecret"]
                        })
                        
                        d1["customApplicationCredentials"].append({
                            "name" : "cui-cred",
                            "secretName": crData["status"]["consumerUICredentialSecret"]
                        })
                        
                        d1["customApplicationCredentials"].append({
                            "name" : "dsgr-cred",
                            "secretName": crData["status"]["designerCredentialSecret"]
                        })
                        
                        d1["customApplicationCredentials"].append({
                            "name" : "juhu-cred",
                            "secretName": crData["status"]["juhuCredentialSecret"]
                        })
                        
                        d1["customApplicationCredentials"].append({
                            "name" : "cli-cred",
                            "secretName": crData["status"]["toolkitCredentialSecret"]
                        })
                        
                        d1["customApplicationCredentials"].append({
                            "name" : "ui-cred",
                            "secretName": crData["status"]["uiCredentialSecret"]
                        })

                        #governanceCredentialSecret added from 10.0.5.3
                        if "governanceCredentialSecret" in crData["status"]:
                            d1["customApplicationCredentials"].append({
                                "name" : "governance-cred",
                                "secretName": crData["status"]["governanceCredentialSecret"]
                            })

                        #discoveryCredentialSecret added from 10.0.7
                        if "discoveryCredentialSecret" in crData["status"]:
                            d1["customApplicationCredentials"].append({
                                "name" : "discovery-cred",
                                "secretName": crData["status"]["discoveryCredentialSecret"]
                            })
                        
                        d1["siteName"] = crData["spec"]["siteName"]
                        d1["versionSpec"] = crData["spec"]["version"]
                        d1["versionReconciled"] = crData["status"]["versions"]["reconciled"]
                        d1["name"] = crData["metadata"]["name"]
                        if "originalUID" in crData["spec"]:
                            d1["originalUID"] = crData["spec"]["originalUID"]
                    
                        # management database backup properties
                        d1["databaseBackup"] = crData["spec"]["databaseBackup"]
                        #if "protocol" in d1["databaseBackup"]:
                        #    del d1["databaseBackup"]["protocol"] # not needed in 10.0.7 edb

                        pgclusters = runKubernetesCommand("get cluster --no-headers", eachNamespace, True) # edb
                        if pgclusters != None and pgclusters != "" and pgclusters.lower().startswith("error") == False:
                            pgclusters = pgclusters.splitlines()
                            if len(pgclusters) == 1:
                                d1["pgclusterName"] = pgclusters[0][0:pgclusters[0].index(" ")]
                            else:
                                for each_pg_name in pgclusters:
                                    if "keycloak" not in each_pg_name:
                                        each_pg_name = each_pg_name.strip()
                                        each_pg_name = each_pg_name[0:each_pg_name.index(" ")]
                                        d1["pgclusterName"] = each_pg_name
                                        break

                        if args.export_cert:
                            os.makedirs(DATA_DIR + "/" + mgmtSubsystemName + "/" + "cert_internal" , mode=0o755, exist_ok=True)
                            os.makedirs(DATA_DIR + "/" + mgmtSubsystemName + "/" + "cert_frontend" , mode=0o755, exist_ok=True)
                            mgmt_cert_internal_dir = DATA_DIR + "/" + mgmtSubsystemName + "/cert_internal/"
                            mgmt_cert_frontend_dir = DATA_DIR + "/" + mgmtSubsystemName + "/cert_frontend/"

                            if "status"in crData and "serviceCASecret" in crData["status"] and "serviceClientSecret" in crData["status"] and "serviceServerSecret" in crData["status"]:
                                d1["customCertificates"] = []
                                d1["customCertificates"].append({
                                    "name": "caCertificate",
                                    "secretName": crData["status"]["serviceCASecret"]
                                })
                                d1["customCertificates"].append({
                                    "name": "serverCertificate",
                                    "secretName": crData["status"]["serviceServerSecret"]
                                })
                                d1["customCertificates"].append({
                                    "name": "clientCertificate",
                                    "secretName": crData["status"]["serviceClientSecret"]
                                })
                                saveSecret(eachNamespace, crData["status"]["serviceCASecret"], mgmt_cert_internal_dir)
                                saveSecret(eachNamespace, crData["status"]["serviceServerSecret"], mgmt_cert_internal_dir)
                                saveSecret(eachNamespace, crData["status"]["serviceClientSecret"], mgmt_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["serviceCASecret"], mgmt_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["serviceServerSecret"], mgmt_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["serviceClientSecret"], mgmt_cert_internal_dir)

                            if "status"in crData and "dbClientSecrets" in crData["status"]:
                                for each in crData["status"]["dbClientSecrets"]:
                                    if each["name"] == "postgres":
                                        d1["customCertificates"].append({
                                            "name": "dbClientPostgres",
                                            "secretName": each["secretName"]
                                        })
                                    if each["name"] == "replicator":
                                        d1["customCertificates"].append({
                                            "name": "dbClientReplicator",
                                            "secretName": each["secretName"]
                                        })
                                    if each["name"] == "pgbouncer":
                                        d1["customCertificates"].append({
                                            "name": "dbClientPgbouncer",
                                            "secretName": each["secretName"]
                                        })
                                    if each["name"] == "apicuser":
                                        d1["customCertificates"].append({
                                            "name": "dbClientApicuser",
                                            "secretName": each["secretName"]
                                        })
                                    if each["name"] == "primaryuser":
                                        d1["customCertificates"].append({
                                            "name": "dbClientPrimaryuser",
                                            "secretName": each["secretName"]
                                        })
                                    saveSecret(eachNamespace, each["secretName"], mgmt_cert_internal_dir)
                                    saveCertificate(eachNamespace, each["secretName"], mgmt_cert_internal_dir)

                            if "natsTlsSecret" in crData["status"] and crData["status"]["natsTlsSecret"] != None:
                                d1["customCertificates"].append({
                                    "name": "NATSTLSCertificate",
                                    "secretName": crData["status"]["natsTlsSecret"]
                                })
                                saveSecret(eachNamespace, crData["status"]["natsTlsSecret"], mgmt_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["natsTlsSecret"], mgmt_cert_internal_dir)

                            if "pgoTlsSecret" in crData["status"] and crData["status"]["pgoTlsSecret"] != None:
                                d1["customCertificates"].append({
                                    "name": "PGOTLSCertificate",
                                    "secretName": crData["status"]["pgoTlsSecret"]
                                })
                                saveSecret(eachNamespace, crData["status"]["pgoTlsSecret"], mgmt_cert_internal_dir)
                                saveCertificate(eachNamespace, "postgres-operator", mgmt_cert_internal_dir)

                            if "dbServerSecret" in crData["status"] and crData["status"]["dbServerSecret"] != None:
                                d1["customCertificates"].append({
                                    "name": "dbServerCertificate",
                                    "secretName": crData["status"]["dbServerSecret"]
                                })
                                saveSecret(eachNamespace, crData["status"]["dbServerSecret"], mgmt_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["dbServerSecret"], mgmt_cert_internal_dir)

                            if "dbReplicationSecret" in crData["status"] and crData["status"]["dbReplicationSecret"] != None:
                                d1["customCertificates"].append({
                                    "name": "dbReplicationCertificate",
                                    "secretName": crData["status"]["dbReplicationSecret"]
                                })
                                saveSecret(eachNamespace, crData["status"]["dbReplicationSecret"], mgmt_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["dbReplicationSecret"], mgmt_cert_internal_dir)

                            if "pgBouncerServerSecret" in crData["status"] and crData["status"]["pgBouncerServerSecret"] != None:
                                d1["customCertificates"].append({
                                    "name": "pgBouncerServerCertificate",
                                    "secretName": crData["status"]["pgBouncerServerSecret"]
                                })
                                saveSecret(eachNamespace, crData["status"]["pgBouncerServerSecret"], mgmt_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["pgBouncerServerSecret"], mgmt_cert_internal_dir)

                            if "status"in crData and "endpoints" in crData["status"]:
                                for each in crData["status"]["endpoints"]:
                                    saveSecret(eachNamespace, each["secretName"], mgmt_cert_frontend_dir)
                                    saveCertificate(eachNamespace, each["secretName"], mgmt_cert_frontend_dir)
                                    d1[each["name"]] =  each["secretName"]

                            if "analytics" in crData["spec"] and "ingestion" in crData["spec"]["analytics"] and "secretName" in crData["spec"]["analytics"]["ingestion"]:
                                d1["analytics_ingestion_client"] =  crData["spec"]["analytics"]["ingestion"]["secretName"]
                                saveSecret(eachNamespace, d1["analytics_ingestion_client"] , mgmt_cert_frontend_dir)
                                saveCertificate(eachNamespace, d1["analytics_ingestion_client"] , mgmt_cert_frontend_dir)

                            if "portal" in crData["spec"] and "admin" in crData["spec"]["portal"] and "secretName" in crData["spec"]["portal"]["admin"]:
                                d1["portal_admin_client"] =  crData["spec"]["portal"]["admin"]["secretName"]
                                saveSecret(eachNamespace, d1["portal_admin_client"] , mgmt_cert_frontend_dir)
                                saveCertificate(eachNamespace, d1["portal_admin_client"] , mgmt_cert_frontend_dir)

                            if "gateway" in crData["spec"] and "client" in crData["spec"]["gateway"] and "secretName" in crData["spec"]["gateway"]["client"]:
                                d1["gateway_client_client"] =  crData["spec"]["gateway"]["client"]["secretName"]
                                saveSecret(eachNamespace, d1["gateway_client_client"] , mgmt_cert_frontend_dir)
                                saveCertificate(eachNamespace, d1["gateway_client_client"] , mgmt_cert_frontend_dir)


                        config["management_subsystem"][mgmtSubsystemName] = d1
                    
                        # save database backup credentials secret for management subsystem
                        if "databaseBackup" in crData["spec"] and "credentials" in crData["spec"]["databaseBackup"]:
                            print ("SAVING DATABASE BACKUP CREDENTIALS SECRET FOR MANAGEMENT SUBSYSTEM::")
                            secretData = runKubernetesCommand("get secret " + d1["databaseBackup"]["credentials"] + " -o yaml", eachNamespace)
                            secretData = yaml.safe_load(secretData)
                            if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                            if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                            if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                            if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                            with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + d1["databaseBackup"]["credentials"] + ".yaml", 'w') as secretFile:
                                yaml.dump(secretData, secretFile, default_flow_style=False)
                    
                        # save encryptionSecret for management subsystem
                        print ("SAVING ENCRYPTION SECRET FOR MANAGEMENT SUBSYSTEM::")
                        secretData = runKubernetesCommand("get secret " + crData["status"]["encryptionSecret"] + " -o yaml", eachNamespace)
                        secretData = yaml.safe_load(secretData)
                        if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                        if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                        if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                        if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                        with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + crData["status"]["encryptionSecret"] + ".yaml", 'w') as secretFile:
                            yaml.dump(secretData, secretFile, default_flow_style=False)
                    
                        # client credential secret (atmCredentialSecret)
                        print ("SAVING atmCredentialSecret FOR MANAGEMENT SUBSYSTEM::")
                        secretData = runKubernetesCommand("get secret " + crData["status"]["atmCredentialSecret"] + " -o yaml", eachNamespace)
                        secretData = yaml.safe_load(secretData)
                        if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                        if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                        if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                        if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                        if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                        #print (secretData)
                        with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + crData["status"]["atmCredentialSecret"] + ".yaml", 'w') as secretFile:
                            yaml.dump(secretData, secretFile, default_flow_style=False)
                    
                        # client credential secret (consumerToolkitCredentialSecret)
                        print ("SAVING consumerToolkitCredentialSecret FOR MANAGEMENT SUBSYSTEM::")
                        secretData = runKubernetesCommand("get secret " + crData["status"]["consumerToolkitCredentialSecret"] + " -o yaml", eachNamespace)
                        secretData = yaml.safe_load(secretData)
                        if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                        if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                        if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                        if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                        if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                        #print (secretData)
                        with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + crData["status"]["consumerToolkitCredentialSecret"] + ".yaml", 'w') as secretFile:
                            yaml.dump(secretData, secretFile, default_flow_style=False)
                    
                        # client credential secret (consumerUICredentialSecret)
                        print ("SAVING consumerUICredentialSecret FOR MANAGEMENT SUBSYSTEM")
                        secretData = runKubernetesCommand("get secret " + crData["status"]["consumerUICredentialSecret"] + " -o yaml", eachNamespace)
                        secretData = yaml.safe_load(secretData)
                        if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                        if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                        if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                        if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                        if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                        #print (secretData)
                        with open(DATA_DIR + "/" + subsystemName + "/" + crData["status"]["consumerUICredentialSecret"] + ".yaml", 'w') as secretFile:
                            yaml.dump(secretData, secretFile, default_flow_style=False)
                    
                        # client credential secret (designerCredentialSecret)
                        print ("SAVING designerCredentialSecret FOR MANAGEMENT SUBSYSTEM::")
                        secretData = runKubernetesCommand("get secret " + crData["status"]["designerCredentialSecret"] + " -o yaml", eachNamespace)
                        secretData = yaml.safe_load(secretData)
                        if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                        if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                        if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                        if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                        if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                        #print (secretData)
                        with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + crData["status"]["designerCredentialSecret"] + ".yaml", 'w') as secretFile:
                            yaml.dump(secretData, secretFile, default_flow_style=False)
                    
                        # client credential secret (juhuCredentialSecret)
                        print ("SAVING juhuCredentialSecret FOR MANAGEMENT SUBSYSTEM::")
                        secretData = runKubernetesCommand("get secret " + crData["status"]["juhuCredentialSecret"] + " -o yaml", eachNamespace)
                        secretData = yaml.safe_load(secretData)
                        if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                        if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                        if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                        if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                        if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                        #print (secretData)
                        with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + crData["status"]["juhuCredentialSecret"] + ".yaml", 'w') as secretFile:
                            yaml.dump(secretData, secretFile, default_flow_style=False)
                        
                        # client credential secret (toolkitCredentialSecret)
                        print ("SAVING toolkitCredentialSecret FOR MANAGEMENT SUBSYSTEM::")
                        secretData = runKubernetesCommand("get secret " + crData["status"]["toolkitCredentialSecret"] + " -o yaml", eachNamespace)
                        secretData = yaml.safe_load(secretData)
                        if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                        if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                        if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                        if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                        if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                        #print (secretData)
                        with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + crData["status"]["toolkitCredentialSecret"] + ".yaml", 'w') as secretFile:
                            yaml.dump(secretData, secretFile, default_flow_style=False)
                    
                        # client credential secret (uiCredentialSecret)
                        print ("SAVING uiCredentialSecret FOR MANAGEMENT SUBSYSTEM::")
                        secretData = runKubernetesCommand("get secret " + crData["status"]["uiCredentialSecret"] + " -o yaml", eachNamespace)
                        secretData = yaml.safe_load(secretData)
                        if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                        if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                        if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                        if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                        if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                        #print (secretData)
                        with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + crData["status"]["uiCredentialSecret"] + ".yaml", 'w') as secretFile:
                            yaml.dump(secretData, secretFile, default_flow_style=False)

                        #governanceCredentialSecret added from 10.0.5.3
                        if "governanceCredentialSecret" in crData["status"]:
                            # client credential secret (governanceCredentialSecret)
                            print ("SAVING governanceCredentialSecret FOR MANAGEMENT SUBSYSTEM::")
                            secretData = runKubernetesCommand("get secret " + crData["status"]["governanceCredentialSecret"] + " -o yaml", eachNamespace)
                            secretData = yaml.safe_load(secretData)
                            if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                            if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                            if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                            if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                            if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                            #print (secretData)
                            with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + crData["status"]["governanceCredentialSecret"] + ".yaml", 'w') as secretFile:
                                yaml.dump(secretData, secretFile, default_flow_style=False)

                        #discoveryCredentialSecret added from 10.0.7
                        if "discoveryCredentialSecret" in crData["status"]:
                            # client credential secret (discoveryCredentialSecret)
                            print ("SAVING discoveryCredentialSecret FOR MANAGEMENT SUBSYSTEM::")
                            secretData = runKubernetesCommand("get secret " + crData["status"]["discoveryCredentialSecret"] + " -o yaml", eachNamespace)
                            secretData = yaml.safe_load(secretData)
                            if "ownerReferences" in secretData["metadata"]: del secretData["metadata"]["ownerReferences"]
                            if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                            if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                            if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                            if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                            #print (secretData)
                            with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + crData["status"]["discoveryCredentialSecret"] + ".yaml", 'w') as secretFile:
                                yaml.dump(secretData, secretFile, default_flow_style=False)


                        # save the ingress-ca secret and certificate for k8s/OCP/CP4I
                        if args.export_cert:
                            print ("SAVING ingress-ca certificate and secret::")
                            ingressCACert = runKubernetesCommand("get certificate | grep ingress-ca", eachNamespace, True, 1, False)
                            if ingressCACert != None and ingressCACert != "" and ingressCACert.lower().startswith("error") == False:
                                ingressCACert = ingressCACert.strip()
                                ingressCACert = ingressCACert.splitlines()
                                if len(ingressCACert) <=0 or len(ingressCACert) > 1:
                                    print ("Time when error occurred :", time.asctime())
                                    sys.exit("ERROR : Number of ingress-ca certificates found is NOT EQUAL TO 1. Exiting. Number of certificates found : {} the names are : {} ".format(len(ingressCACert), ingressCACert))
                                ingressCACertName = ingressCACert[0][0:ingressCACert[0].index(" ")]
                                ingressCACertYaml = runKubernetesCommand("get certificate " + ingressCACertName + " -o yaml", eachNamespace, True)
                                ingressCACertYaml = yaml.safe_load(ingressCACertYaml)
                                if "creationTimestamp" in ingressCACertYaml["metadata"]: del ingressCACertYaml["metadata"]["creationTimestamp"]
                                if "annotations" in ingressCACertYaml["metadata"]: del ingressCACertYaml["metadata"]["annotations"]
                                if "generation" in ingressCACertYaml["metadata"]: del ingressCACertYaml["metadata"]["generation"]
                                if "managedFields" in ingressCACertYaml["metadata"]: del ingressCACertYaml["metadata"]["managedFields"]
                                if "namespace" in ingressCACertYaml["metadata"]: del ingressCACertYaml["metadata"]["namespace"]
                                if "resourceVersion" in ingressCACertYaml["metadata"]: del ingressCACertYaml["metadata"]["resourceVersion"]
                                if "selfLink" in ingressCACertYaml["metadata"]: del ingressCACertYaml["metadata"]["selfLink"]
                                if "uid" in ingressCACertYaml["metadata"]: del ingressCACertYaml["metadata"]["uid"]
                                if "ownerReferences" in ingressCACertYaml["metadata"]: del ingressCACertYaml["metadata"]["ownerReferences"]
                                if "status" in ingressCACertYaml: del ingressCACertYaml["status"]
                                icFileName = DATA_DIR + "/" + mgmtSubsystemName + "/" + ingressCACertName + "_cert.yaml"
                                with open(icFileName, 'w') as f1:
                                    yaml.dump(ingressCACertYaml, f1, default_flow_style=False)
                                print("ingress-ca certificate location : ", icFileName)

                                ingressCASecretName = ingressCACertYaml["spec"]["secretName"]
                                ingressCASecretYaml = runKubernetesCommand("get secret " + ingressCASecretName + " -o yaml", eachNamespace, True)
                                ingressCASecretYaml = yaml.safe_load(ingressCASecretYaml)
                                if "creationTimestamp" in ingressCASecretYaml["metadata"]: del ingressCASecretYaml["metadata"]["creationTimestamp"]
                                if "managedFields" in ingressCASecretYaml["metadata"]: del ingressCASecretYaml["metadata"]["managedFields"]
                                if "annotations" in ingressCASecretYaml["metadata"]: del ingressCASecretYaml["metadata"]["annotations"]
                                if "namespace" in ingressCASecretYaml["metadata"]: del ingressCASecretYaml["metadata"]["namespace"]
                                if "resourceVersion" in ingressCASecretYaml["metadata"]: del ingressCASecretYaml["metadata"]["resourceVersion"]
                                if "selfLink" in ingressCASecretYaml["metadata"]: del ingressCASecretYaml["metadata"]["selfLink"]
                                if "uid" in ingressCASecretYaml["metadata"]: del ingressCASecretYaml["metadata"]["uid"]
                                isFileName = DATA_DIR + "/" + mgmtSubsystemName + "/" + ingressCASecretName + "_secret.yaml"
                                with open(isFileName, 'w') as f1:
                                    yaml.dump(ingressCASecretYaml, f1, default_flow_style=False)

                                config["management_subsystem"][mgmtSubsystemName]["ingress_ca_cert"] = ingressCACertName + "_cert.yaml"
                                config["management_subsystem"][mgmtSubsystemName]["ingress_ca_secret"] = ingressCASecretName + "_secret.yaml"
                                print("ingress-ca secret location : ", isFileName)
                                print()
                            else:
                                print("ACTION OUTPUT : ingress-ca secret NOT found.")
                                isAppliance = False
                                apicDeployYaml = runKubernetesCommand("get deploy ibm-apiconnect -o yaml", "default", True, 0, False)
                                if apicDeployYaml != None and apicDeployYaml != "" and apicDeployYaml.lower().startswith("error") == False:
                                    apicDeployYaml = yaml.safe_load(apicDeployYaml)
                                    if "spec" in apicDeployYaml and "template" in apicDeployYaml["spec"] and "spec" in apicDeployYaml["spec"]["template"] and "containers" in apicDeployYaml["spec"]["template"]["spec"]:
                                        containers = apicDeployYaml["spec"]["template"]["spec"]["containers"]
                                        for eachC in containers:
                                            if "name" in eachC and eachC["name"] == "ibm-apiconnect" and "env" in eachC:
                                                print("ibm-apiconnect container found")
                                                envs = eachC["env"]
                                                for eachenv in envs:
                                                    if eachenv["name"] == "APPLIANCE" and eachenv["value"] == "true":
                                                        isAppliance = True
                                                        break
                                            if isAppliance: break

                                if isAppliance:
                                    print("ACTION OUTPUT : is appliance = true")

                                    if args.export_cert and os.path.exists("apiconnect-up-v10.yml") == False: 
                                        print ("Time when error occurred :", time.asctime())
                                        print ("Copy the script to project directory and upload the project directory to appliance and run from that directory.")
                                        sys.exit("ERROR : export_cert flag is set and NOT running the script from project directory. apiconnect-up-v10.yml NOT found. Exiting.")

                                    #check for apicup
                                    output = runCommand("apicup version --accept-license", True, 0, False)
                                    if output != None or output != "" or output.startswith("APIConnect") == True:
                                        print("ACTION OUTPUT : apicup installer found in the path.")
                                        rootCACert = runCommand("apicup certs get " + mgmtSubsystemName + " root-ca --type cert", True)
                                        if rootCACert != None: rootCACert = rootCACert.strip()
                                        rootCACertBase64Encoded = base64.b64encode(rootCACert.encode('ascii'))
                                        rootCACertBase64Encoded = rootCACertBase64Encoded.decode("ascii")

                                        rootCAKey = runCommand("apicup certs get " + mgmtSubsystemName + " root-ca --type key", True)
                                        if rootCAKey != None: rootCAKey = rootCAKey.strip()
                                        rootCAKeyBase64Encoded = base64.b64encode(rootCAKey.encode('ascii'))
                                        rootCAKeyBase64Encoded = rootCAKeyBase64Encoded.decode("ascii")

                                        rootCASecret = {
                                            "apiVersion": "v1",
                                            "data": {
                                                "ca.crt": rootCACertBase64Encoded,
                                                "tls.crt": rootCACertBase64Encoded,
                                                "tls.key": rootCAKeyBase64Encoded
                                            },
                                            "kind": "Secret",
                                            "metadata": {
                                                "name": "root-ca"
                                            },
                                            "type": "kubernetes.io/tls"
                                        }
                                        rootcaFileName = DATA_DIR + "/" + mgmtSubsystemName + "/root-ca_secret.yaml"
                                        with open(rootcaFileName, 'w') as f1:
                                            yaml.dump(rootCASecret, f1, default_flow_style=False)
                                        print("root-ca secret location : ", rootcaFileName)
                                        print()

                                        ingressCACert = runCommand("apicup certs get " + mgmtSubsystemName + " ingress-ca --type cert", True)
                                        if ingressCACert != None: ingressCACert = ingressCACert.strip()
                                        ingressCACertBase64Encoded = base64.b64encode(ingressCACert.encode('ascii'))
                                        ingressCACertBase64Encoded = ingressCACertBase64Encoded.decode("ascii")

                                        ingressCAKey = runCommand("apicup certs get " + mgmtSubsystemName + " ingress-ca --type key", True)
                                        if ingressCAKey != None: ingressCAKey = ingressCAKey.strip()
                                        ingressCAKeyBase64Encoded = base64.b64encode(ingressCAKey.encode('ascii'))
                                        ingressCAKeyBase64Encoded = ingressCAKeyBase64Encoded.decode("ascii")

                                        ingressCASecret = {
                                            "apiVersion": "v1",
                                            "data": {
                                                "ca.crt": rootCACertBase64Encoded,
                                                "tls.crt": ingressCACertBase64Encoded,
                                                "tls.key": ingressCAKeyBase64Encoded
                                            },
                                            "kind": "Secret",
                                            "metadata": {
                                                "name": "root-ca"
                                            },
                                            "type": "kubernetes.io/tls"
                                        }
                                        ingressCAFileName = DATA_DIR + "/" + mgmtSubsystemName + "/ingress-ca_secret.yaml"
                                        with open(ingressCAFileName, 'w') as f1:
                                            yaml.dump(ingressCASecret, f1, default_flow_style=False)
                                        print("ingress-ca secret location : ", ingressCAFileName)

                                        config["management_subsystem"][mgmtSubsystemName]["root_ca_secret"] = "root-ca_secret.yaml"
                                        config["management_subsystem"][mgmtSubsystemName]["ingress_ca_secret"] = "ingress-ca_secret.yaml"
                                        print()
                                    else:
                                        print("ACTION OUTPUT : apicup installer NOT FOUND in the path.")
                                else:
                                    print("ACTION OUTPUT : is appliance = false")
                        
                        #check for cp4i registrations and save secret topcr-cp4i-creds
                        if os.path.exists(DATA_TEMP_DIR + "/cp4i.yaml"):
                            os.remove(DATA_TEMP_DIR + "/cp4i.yaml")
                        cp4iRegistration = runCommand("apic registrations:get --server " + cloudAdminServer + " cp4i --output " + DATA_TEMP_DIR, True, 0, False)
                        if cp4iRegistration != None and cp4iRegistration != "" and cp4iRegistration.lower().startswith("error") == False:
                            print ("SAVING topcr-cp4i-creds secret as this is CP4I system::")
                            cp4iCredsSecretName = runKubernetesCommand("get secret | grep cp4i-creds", eachNamespace)
                            if cp4iCredsSecretName != None and cp4iCredsSecretName != "":
                                cp4iCredsSecretName = cp4iCredsSecretName.strip()
                                cp4iCredsSecretName = cp4iCredsSecretName[0:cp4iCredsSecretName.index(" ")]
                                cp4iCredsSecretData = runKubernetesCommand("get secret " + cp4iCredsSecretName + " -o yaml", eachNamespace)
                                cp4iCredsSecretData = yaml.safe_load(cp4iCredsSecretData)
                                if "namespace" in cp4iCredsSecretData["metadata"]: del cp4iCredsSecretData["metadata"]["namespace"]
                                if "creationTimestamp" in cp4iCredsSecretData["metadata"]: del cp4iCredsSecretData["metadata"]["creationTimestamp"]
                                if "ownerReferences" in cp4iCredsSecretData["metadata"]: del cp4iCredsSecretData["metadata"]["ownerReferences"]
                                if "managedFields" in cp4iCredsSecretData["metadata"]: del cp4iCredsSecretData["metadata"]["managedFields"]
                                if "selfLink" in cp4iCredsSecretData["metadata"]: del cp4iCredsSecretData["metadata"]["selfLink"]
                                if "uid" in cp4iCredsSecretData["metadata"]: del cp4iCredsSecretData["metadata"]["uid"]
                                if "resourceVersion" in cp4iCredsSecretData["metadata"]: del cp4iCredsSecretData["metadata"]["resourceVersion"]
                                #print (cp4iCredsSecretData)
                                with open(DATA_DIR + "/" + mgmtSubsystemName + "/" + cp4iCredsSecretName + ".yaml", 'w') as cp4iCredsFile:
                                    yaml.dump(cp4iCredsSecretData, cp4iCredsFile, default_flow_style=False)
                                config["management_subsystem"][mgmtSubsystemName]["cp4i_registration_secret"] = cp4iCredsSecretName + ".yaml"

                        print()
                        if args.skip_mgmt_backup == False:
                            print ("CREATE MANAGEMENT BACKUP ::")
                            print ("***************************")
                            createManagementEDBBackup(eachNamespace)
                            # createManagementBackup(eachNamespace)
                        else:
                            print ("ACTION OUTPUT : Skipping management backup. skip_mgmt_backup flag is set.")

                        print()
                        if args.export_data_for_validation == True:
                            exportDataForValidation ()
                            config["management_subsystem"][mgmtSubsystemName]["export_data_for_validation"] = True
                            config["management_subsystem"][mgmtSubsystemName]["export_data_orgs_list"] = []

                    else:
                        print("ACTION OUTPUT : Could not save management info. Management namespace not provided or management subsystem not installed.")
                    
                    
                if subsystems[i] == "ptl":
                    if subsystemName != None:
                    
                        portalSubsystemName = subsystemName
                    
                        # check for backup configuration
                        if args.skip_ptl_backup == False:
                            print ("Validating database backup configuration for portal subsystem")
                            if "portalBackup" not in crData["spec"]:
                                print ("Time when error occurred :", time.asctime())
                                sys.exit("ERROR : Portal subsystem ({}) validation failed. Database backup not configured. Exiting...".format(portalSubsystemName))
                            else:
                                portalBackup = crData["spec"]["portalBackup"]
                                if "protocol" not in portalBackup or "host" not in portalBackup or "path" not in portalBackup or "credentials" not in portalBackup:
                                    print ("Time when error occurred :", time.asctime())
                                    sys.exit("ERROR : Portal subsystem ({}) validation failed. Database backup not configured. Check host, credentials, path, protocol.  Exiting...".format(portalSubsystemName))
                                if portalBackup["protocol"] == "sftp" and "port" not in portalBackup:
                                    print ("Time when error occurred :", time.asctime())
                                    sys.exit("ERROR : Portal subsystem ({}) validation failed. Database backup not configured. Check port number.  Exiting...".format(portalSubsystemName))

                        for eachSecret in portalSecrets:
                            if eachSecret not in crData["status"]:
                                print ("Time when error occurred :", time.asctime())
                                sys.exit("ERROR : Secret {} not present in the portal CR status for subsystem with name {}".format(eachSecret, portalSubsystemName))
                            
                        d1 = {}
                        if portalSubsystemName in config_portal["portal_subsystem"]:
                            d1 = config_portal["portal_subsystem"][portalSubsystemName]

                        d1["encryptionSecret"] = {
                            "secretName": crData["status"]["encryptionSecret"]
                        }
                        
                        d1["siteName"] = crData["spec"]["siteName"]
                        d1["name"] = crData["metadata"]["name"]
                        if "originalUID" in crData["spec"]:
                            d1["originalUID"] = crData["spec"]["originalUID"]
                    
                        # portal backup properties
                        if "portalBackup" in crData["spec"]:
                            d1["portalBackup"] = crData["spec"]["portalBackup"]
                        
                        if args.export_cert:
                            os.makedirs(DATA_DIR + "/" + portalSubsystemName + "/" + "cert_internal" , mode=0o755, exist_ok=True)
                            os.makedirs(DATA_DIR + "/" + portalSubsystemName + "/" + "cert_frontend" , mode=0o755, exist_ok=True)
                            ptl_cert_internal_dir = DATA_DIR + "/" + portalSubsystemName + "/cert_internal/"
                            ptl_cert_frontend_dir = DATA_DIR + "/" + portalSubsystemName + "/cert_frontend/"

                            if "status"in crData and "serviceCASecret" in crData["status"] and "serviceClientSecret" in crData["status"] and "serviceServerSecret" in crData["status"]:
                                d1["customCertificates"] = []
                                d1["customCertificates"].append({
                                    "name": "caCertificate",
                                    "secretName": crData["status"]["serviceCASecret"]
                                })
                                d1["customCertificates"].append({
                                    "name": "serverCertificate",
                                    "secretName": crData["status"]["serviceServerSecret"]
                                })
                                d1["customCertificates"].append({
                                    "name": "clientCertificate",
                                    "secretName": crData["status"]["serviceClientSecret"]
                                })
                                saveCertificate(eachNamespace, crData["status"]["serviceCASecret"], ptl_cert_internal_dir)
                                saveSecret(eachNamespace, crData["status"]["serviceCASecret"], ptl_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["serviceServerSecret"], ptl_cert_internal_dir)
                                saveSecret(eachNamespace, crData["status"]["serviceServerSecret"], ptl_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["serviceClientSecret"], ptl_cert_internal_dir)
                                saveSecret(eachNamespace, crData["status"]["serviceClientSecret"], ptl_cert_internal_dir)

                            if "status"in crData and "endpoints" in crData["status"]:
                                for each in crData["status"]["endpoints"]:
                                    saveCertificate(eachNamespace, each["secretName"], ptl_cert_frontend_dir)
                                    saveSecret(eachNamespace, each["secretName"], ptl_cert_frontend_dir)
                                    d1[each["name"]] =  each["secretName"]

                        config_portal["portal_subsystem"][portalSubsystemName] = d1
                    
                        # save database backup credentials secret for portal subsystem
                        if "portalBackup" in crData["spec"] and "credentials" in crData["spec"]["portalBackup"]:
                            print ("SAVING DATABASE BACKUP CREDENTIALS SECRET FOR PORTAL SUBSYSTEM::")
                            secretData = runKubernetesCommand("get secret " + d1["portalBackup"]["credentials"] + " -o yaml", eachNamespace)
                            secretData = yaml.safe_load(secretData)
                            if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                            if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                            if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                            if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                            with open(DATA_DIR + "/" + portalSubsystemName + "/" + d1["portalBackup"]["credentials"] + ".yaml", 'w') as secretFile:
                                yaml.dump(secretData, secretFile, default_flow_style=False)
                    
                        # save encryptionSecret for portal subsystem
                        print ("SAVING ENCRYPTION SECRET FOR PORTAL SUBSYSTEM::")
                        secretData = runKubernetesCommand("get secret " + crData["status"]["encryptionSecret"] + " -o yaml", eachNamespace)
                        secretData = yaml.safe_load(secretData)
                        if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
                        if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
                        if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
                        if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
                        with open(DATA_DIR + "/" + portalSubsystemName + "/" + crData["status"]["encryptionSecret"] + ".yaml", 'w') as secretFile:
                            yaml.dump(secretData, secretFile,  default_flow_style=False)
                        
                        print()	
                        if args.skip_ptl_backup == False:
                            print ("CREATE PORTAL BACKUP ::")
                            print ("***********************")
                            createPortalBackup(eachNamespace)
                        else:
                            print ("ACTION OUTPUT : Skipping portal backup. skip_ptl_backup flag is set.")

                    else:
                        print("ACTION OUTPUT : Could not save portal info. Portal namespace not provided or portal subsystem not installed.")
                
                if subsystems[i] == "gw":
                    if subsystemName != None:
                        gwSubsystemName = subsystemName
                        if args.export_cert:
                            os.makedirs(DATA_DIR + "/" + gwSubsystemName + "/" + "cert_internal" , mode=0o755, exist_ok=True)
                            os.makedirs(DATA_DIR + "/" + gwSubsystemName + "/" + "cert_frontend" , mode=0o755, exist_ok=True)
                            gw_cert_internal_dir = DATA_DIR + "/" + gwSubsystemName + "/cert_internal/"
                            gw_cert_frontend_dir = DATA_DIR + "/" + gwSubsystemName + "/cert_frontend/"

                            d3 = {}
                            if gwSubsystemName in config["gateway_subsystem"]:
                                d3 = config["gateway_subsystem"][gwSubsystemName]
                            if "apicGatewayServiceTLS" in crData["spec"] and "secretName" in crData["spec"]["apicGatewayServiceTLS"]:
                                d3["apicGatewayServiceTLS"] =  crData["spec"]["apicGatewayServiceTLS"]["secretName"]
                                saveSecret(eachNamespace, d3["apicGatewayServiceTLS"] , gw_cert_frontend_dir)
                                saveCertificate(eachNamespace, d3["apicGatewayServiceTLS"] , gw_cert_frontend_dir)

                            if "apicGatewayPeeringTLS" in crData["spec"] and "secretName" in crData["spec"]["apicGatewayPeeringTLS"]:
                                d3["apicGatewayPeeringTLS"] =  crData["spec"]["apicGatewayPeeringTLS"]["secretName"]
                                saveSecret(eachNamespace, d3["apicGatewayPeeringTLS"] , gw_cert_frontend_dir)
                                saveCertificate(eachNamespace, d3["apicGatewayPeeringTLS"] , gw_cert_frontend_dir)

                            if "status"in crData and "endpoints" in crData["status"]:
                                for each in crData["status"]["endpoints"]:
                                    saveCertificate(eachNamespace, each["secretName"], gw_cert_frontend_dir)
                                    saveSecret(eachNamespace, each["secretName"], gw_cert_frontend_dir)
                                    d3[each["name"]] =  each["secretName"]
                            config["gateway_subsystem"][gwSubsystemName] = d3


                if subsystems[i] == "a7s":
                    if subsystemName != None:
                        analyticsSubsystemName = subsystemName
                        if args.export_cert:
                            os.makedirs(DATA_DIR + "/" + analyticsSubsystemName + "/" + "cert_internal" , mode=0o755, exist_ok=True)
                            os.makedirs(DATA_DIR + "/" + analyticsSubsystemName + "/" + "cert_frontend" , mode=0o755, exist_ok=True)
                            a7s_cert_internal_dir = DATA_DIR + "/" + analyticsSubsystemName + "/cert_internal/"
                            a7s_cert_frontend_dir = DATA_DIR + "/" + analyticsSubsystemName + "/cert_frontend/"

                            d2 = {}
                            if analyticsSubsystemName in config["analytics_subsystem"]:
                                d2 = config["analytics_subsystem"][analyticsSubsystemName]
                            if "status"in crData and "serviceCASecret" in crData["status"] and "serviceClientSecret" in crData["status"] and "serviceServerSecret" in crData["status"]:
                                d2["customCertificates"] = []
                                d2["customCertificates"].append({
                                    "name": "caCertificate",
                                    "secretName": crData["status"]["serviceCASecret"]
                                })
                                d2["customCertificates"].append({
                                    "name": "serverCertificate",
                                    "secretName": crData["status"]["serviceServerSecret"]
                                })
                                d2["customCertificates"].append({
                                    "name": "clientCertificate",
                                    "secretName": crData["status"]["serviceClientSecret"]
                                })
                                saveCertificate(eachNamespace, crData["status"]["serviceCASecret"], a7s_cert_internal_dir)
                                saveSecret(eachNamespace, crData["status"]["serviceCASecret"], a7s_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["serviceServerSecret"], a7s_cert_internal_dir)
                                saveSecret(eachNamespace, crData["status"]["serviceServerSecret"], a7s_cert_internal_dir)
                                saveCertificate(eachNamespace, crData["status"]["serviceClientSecret"], a7s_cert_internal_dir)
                                saveSecret(eachNamespace, crData["status"]["serviceClientSecret"], a7s_cert_internal_dir)

                            if "status"in crData and "endpoints" in crData["status"]:
                                for each in crData["status"]["endpoints"]:
                                    saveCertificate(eachNamespace, each["secretName"], a7s_cert_frontend_dir)
                                    saveSecret(eachNamespace, each["secretName"], a7s_cert_frontend_dir)
                                    d2[each["name"]] =  each["secretName"]
                            config["analytics_subsystem"][analyticsSubsystemName] = d2

                if subsystemName != None:
                    # saving subsystem CR
                    print ("ACTION OUTPUT : Saving {} subsystem cr for subsystem name, {}".format(subsystems[i], subsystemName))
                    with open(DATA_DIR + "/" + subsystemName + "/" + subsystems[i] + "_cr.yaml", 'w') as crFile:
                        yaml.dump(crData, crFile, default_flow_style=False)
                
                    # saving config data
                    print ("ACTION OUTPUT : Saving configuration data for {} subsystem with name, {}".format(subsystems[i], subsystemName))
                    if subsystems[i] == "mgmt" or subsystems[i] == "gw" or subsystems[i] == "a7s":
                        with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
                            yaml.dump(config, configFile,  default_flow_style=False)
                    else:
                        with open(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME, 'w') as configFile2:
                            yaml.dump(config_portal, configFile2, default_flow_style=False)
                print()
                print()


def saveCertificate(namespace, name, directoryPath):
    print ("ACTION OUTPUT : Saving certificate with name {} in namespace {} at path {}".format(name, namespace, directoryPath))
    certData = runKubernetesCommand("get certificate " + name + " -o yaml", namespace, True, 2, False)
    if certData != None:
        certData = certData.strip().lower()
        if  "error" not in certData and "not found" not in certData:
            certData = yaml.safe_load(certData)
            if "status" in certData: del certData["status"]
            if "namespace" in certData["metadata"]: del certData["metadata"]["namespace"]
            if "creationTimestamp" in certData["metadata"]: del certData["metadata"]["creationTimestamp"]
            if "generation" in certData["metadata"]: del certData["metadata"]["generation"]
            if "ownerReferences" in certData["metadata"]: del certData["metadata"]["ownerReferences"]
            if "uid" in certData["metadata"]: del certData["metadata"]["uid"]
            if "resourceVersion" in certData["metadata"]: del certData["metadata"]["resourceVersion"]
            with open(directoryPath + "cert_" + name + ".yaml", 'w') as certFile:
                yaml.dump(certData, certFile,  default_flow_style=False)
    else:
        print ("ACTION OUTPUT : Error while saving certificate with name {} in namespace {}. Error : {}".format(name, namespace, certData))


def saveSecret(namespace, name, directoryPath):
    print ("ACTION OUTPUT : Saving secret with name {} in namespace {} at path {}".format(name, namespace, directoryPath))
    secretData = runKubernetesCommand("get secret " + name + " -o yaml", namespace)
    secretData = yaml.safe_load(secretData)
    if "namespace" in secretData["metadata"]: del secretData["metadata"]["namespace"]
    if "annotations" in secretData["metadata"]: del secretData["metadata"]["annotations"]
    if "creationTimestamp" in secretData["metadata"]: del secretData["metadata"]["creationTimestamp"]
    if "uid" in secretData["metadata"]: del secretData["metadata"]["uid"]
    if "resourceVersion" in secretData["metadata"]: del secretData["metadata"]["resourceVersion"]
    with open(directoryPath + "secret_" + name + ".yaml", 'w') as secretFile:
        yaml.dump(secretData, secretFile,  default_flow_style=False)

# management backup
def createManagementBackup(namespace):
    if mgmtSubsystemName != None:
        print("Current backup list:")
        runKubernetesCommand("get managementbackups", namespace)
        print ("managment subsystem name : ", mgmtSubsystemName)
        mgmt_backup["spec"]["clusterName"] = mgmtSubsystemName
        backupFileName = DATA_TEMP_DIR + "/mgmt_backup_cr_" + mgmtSubsystemName + ".yaml"
        with open(backupFileName, 'w') as mgmtBackupFile:
            yaml.dump(mgmt_backup, mgmtBackupFile,  default_flow_style=False)
        print()
        print ("Creating management backup for subsystem with name :: ", mgmtSubsystemName)
        runKubernetesCommand("create -f " + backupFileName, namespace)
        time.sleep(10)
        print ("Get currently running management backups")
        out = runKubernetesCommand("get managementbackups | grep Running | grep create| grep full", namespace, False, 10)
        lines = out.splitlines()
        runningBackups = {}
        for x in lines:
            runningBackups[x[0:x.index(" ")]] = "INPROGRESS"
        
        flag = True
        loopCount = 0
        while flag:
            loopCount = loopCount + 1
            if loopCount >= 120:
                # safe break after 2 hr
                sys.exit ("Timeout after Waiting for management db backup to be completed. Check backup status/configuration and try again")

            print ("Waiting for management database backup to be completed. Current time : ", time.asctime())
            time.sleep(60)
            flag = False
            for eachRunningBackup in runningBackups:
                if runningBackups[eachRunningBackup] == "INPROGRESS":
                    flag = True
                    res = runKubernetesCommand("get managementbackups " + eachRunningBackup + " -o yaml", namespace, True, 0, False)
                    if res != None and res != "" and res.lower().startswith("error") == False:
                        res = yaml.safe_load(res)
                        if res["status"]["phase"] != "Running":
                            runningBackups[eachRunningBackup] = res["status"]["id"] + "         status : " + res["status"]["phase"]                        
                            break
        print ()
        print ("ACTION OUTPUT : Management backup completed. Check status. Below is the name, id and status of the backups.")
        print ("If successful backup, the backup id is saved and will be used during management db restore.")
        for eachRunningBackup in runningBackups:
            print ("NAME : {}  and ID : {}".format(eachRunningBackup, runningBackups[eachRunningBackup]))
            if not runningBackups[eachRunningBackup].endswith("Ready"):
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : Management backup with name({}) and id/status ({}). Exiting...".format(eachRunningBackup, runningBackups[eachRunningBackup]))
            config["management_subsystem"][mgmtSubsystemName]["backupId"] = runningBackups[eachRunningBackup][0:runningBackups[eachRunningBackup].index("F")]
        with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
            yaml.dump(config, configFile, default_flow_style=False)
        print ()
    else:
        print()
        print("ACTION OUTPUT : Could not take management backup. Management namespace not provided or subsystem not installed.")

# management edb backup
def createManagementEDBBackup(namespace):
    mgmtBackups = "backups.postgresql.k8s.enterprisedb.io"
    if mgmtSubsystemName != None:
        print("Current management postgres database backup list:")
        runKubernetesCommand("get " + mgmtBackups, namespace)
        print ("managment subsystem name : ", mgmtSubsystemName)

        edbClusterName = None
        edbClusters = runKubernetesCommand("get cluster --no-headers", namespace)
        if edbClusters != None and edbClusters != "" and edbClusters.lower().startswith("error") == False:
            edbClusters = edbClusters.splitlines()
            if len(edbClusters) == 1:
                edbClusterName = edbClusters[0][0:edbClusters[0].index(" ")]
            else:
                for each_pg_name in edbClusters:
                    each_pg_name = each_pg_name.strip()
                    if "keycloak" not in each_pg_name:
                        edbClusterName = each_pg_name[0:each_pg_name.index(" ")]
                        break

        if edbClusterName == None:
            sys.exit("ERROR : Could not select the management postgres cluster from the namespace. Either postgres cluster not found or multiple postgres clusters found.")

        mgmt_edb_backup["spec"]["cluster"]["name"] = edbClusterName
        mgmt_edb_backup["metadata"]["name"] = "management-backup-" + str(random.randint(0, 99999))
        print ("Postgres cluster name : ", edbClusterName)

        backupFileName = DATA_TEMP_DIR + "/" + mgmt_edb_backup["metadata"]["name"]  + ".yaml"
        with open(backupFileName, 'w') as mgmtBackupFile:
            yaml.dump(mgmt_edb_backup, mgmtBackupFile,  default_flow_style=False)
        print()
        print ("Creating management postgres backup for subsystem with name :: ", mgmtSubsystemName)
        runKubernetesCommand("create -f " + backupFileName, namespace)

        print ("Get currently running management postgres backups")
        out = runKubernetesCommand("get " + mgmtBackups + " | grep " + mgmt_edb_backup["metadata"]["name"] , namespace, False, 10)
        lines = out.splitlines()
        runningBackups = {}
        for x in lines:
            runningBackups[x[0:x.index(" ")]] = "INPROGRESS"

        flag = True
        loopCount = 0
        while flag:
            loopCount = loopCount + 1
            if loopCount >= 120:
                # safe break after 2 hr
                sys.exit ("Timeout after Waiting for management db backup to be completed. Check backup status/configuration and try again")

            print ("Waiting for management postgres database backup to be completed. Current time : ", time.asctime())
            time.sleep(60)
            flag = False
            for eachRunningBackup in runningBackups:
                if runningBackups[eachRunningBackup] == "INPROGRESS":
                    flag = True
                    res = runKubernetesCommand("get " + mgmtBackups + " " + eachRunningBackup + " -o yaml", namespace, True, 0, False)
                    if res != None and res != "" and res.lower().startswith("error") == False:
                        res = yaml.safe_load(res)
                        if res["status"]["phase"] != "Running" and "backupId" in res["status"]:
                            runningBackups[eachRunningBackup] = res["status"]["backupId"] + "|" + res["status"]["serverName"] + "|" + res["status"]["phase"]
                            break
        print ()
        print ("ACTION OUTPUT : Management postgres backup completed. Check status. Below is the name, id and status of the backups.")
        print ("If successful backup, the backup id is saved and will be used during management db restore.")
        for eachRunningBackup in runningBackups:
            print ("NAME : {}  and DETAILS : {}".format(eachRunningBackup, runningBackups[eachRunningBackup]))
            if not runningBackups[eachRunningBackup].endswith("completed"):
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : Management backup with name({}) and DETAILS({}). Exiting...".format(eachRunningBackup, runningBackups[eachRunningBackup]))
            config["management_subsystem"][mgmtSubsystemName]["backupId"] = runningBackups[eachRunningBackup][0:runningBackups[eachRunningBackup].rindex("|")]
        with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
            yaml.dump(config, configFile, default_flow_style=False)
        print ()
    else:
        print()
        print("ACTION OUTPUT : Could not take management backup. Management namespace not provided or subsystem not installed.")


# portal backup
def createPortalBackup(namespace):
    ptlBackups = "portalbackups.portal.apiconnect.ibm.com"
    if portalSubsystemName != None:
        backups1 = runKubernetesCommand("get " + ptlBackups, namespace, True)
        backups1Lines = backups1.splitlines()
        backup1Names = []
        for x in backups1Lines:
            backup1Names.append(x[0:x.index(" ")])
        backups1Lines = None
        backups1 = None
    
        ptl_backup["spec"]["portalCluster"] = portalSubsystemName

        #ptl_backup["spec"]["type"] = "system"
        if ptl_backup["spec"]["type"] == "system":
            sysBackupFileName = DATA_TEMP_DIR + "/portal_system_backup_cr_" + portalSubsystemName + ".yaml"
            with open(sysBackupFileName, 'w') as pb1:
                yaml.dump(ptl_backup, pb1, default_flow_style=False)
            print ("Creating portal system backup for subsystem with name :: ", portalSubsystemName)
            runKubernetesCommand("create -f " + sysBackupFileName, namespace)
            time.sleep(10)

        #ptl_backup["spec"]["type"] = "site"
        if ptl_backup["spec"]["type"] == "site":
            ptl_backup["spec"]["siteName"] = "installed" #all sites
            siteBackupFileName = DATA_TEMP_DIR + "/portal_site_backup_cr_" + portalSubsystemName + ".yaml"
            with open(siteBackupFileName, 'w') as pb2:
                yaml.dump(ptl_backup, pb2, default_flow_style=False)
                print ("Creating portal site backup for subsystem with name :: ", portalSubsystemName)
                runKubernetesCommand("create -f " + siteBackupFileName, namespace)
                time.sleep(10)

        #perform all (both system and site) backup
        backupFileName = DATA_TEMP_DIR + "/portal_backup_cr_" + portalSubsystemName + ".yaml"
        with open(backupFileName, 'w') as portalBackupFile:
            yaml.dump(ptl_backup, portalBackupFile, default_flow_style=False)
        print()
        print ("Creating portal backup for subsystem with name :: ", portalSubsystemName)
        runKubernetesCommand("create -f " + backupFileName, namespace)
        time.sleep(10)
        print ("Get currently running portal backups")
        out = runKubernetesCommand("get " + ptlBackups + " | grep Running | grep create", namespace, False, 10)
        lines = out.splitlines()
        runningBackups = {}
        for x in lines:
            runningBackups[x[0:x.index(" ")]] = "INPROGRESS"
        
        flag = True
        loopCount = 0
        while flag:
            loopCount = loopCount + 1
            if loopCount >= 120:
                # safe break after 2 hr
                sys.exit ("Timeout after Waiting for portal db backup. Check the status of backup and configuration and try again.")

            print ("Waiting for portal system/site backup to be completed. Current time : ", time.asctime())
            time.sleep(60)
            flag = False
            for eachRunningBackup in runningBackups:
                if runningBackups[eachRunningBackup] == "INPROGRESS":
                    flag = True
                    res = runKubernetesCommand("get " + ptlBackups + " " + eachRunningBackup + " -o yaml", namespace, True, 0, False)
                    if res != None and res != "" and res.lower().startswith("error") == False:
                        res = yaml.safe_load(res)
                        if res["status"]["phase"] != "Running":
                            runningBackups[eachRunningBackup] = res["status"]["phase"]
                            break
        print ()
        print ("Portal backup completed. Check status. Below is the name and id of all the backups.")
        for eachRunningBackup in runningBackups:
            print ("NAME : {}  and status : {}".format(eachRunningBackup, runningBackups[eachRunningBackup]))
            if not runningBackups[eachRunningBackup].endswith("Ready"):
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : Portal backup with name({}) and status ({}). Exiting...".format(eachRunningBackup, runningBackups[eachRunningBackup]))
        print ()
        print ()
        print ()
        backups1 = runKubernetesCommand("get " + ptlBackups, namespace, True)
        backups1Lines = backups1.splitlines()
        print ("ACTION OUTPUT : LIST OF PORTAL BACKUPS FOR THIS RUN ::: ")
        print ("The backup ids are saved and they will be used during portal site restore.")
        config_portal["portal_subsystem"][portalSubsystemName]["backupId_sites"] = []
        for eachLine in backups1Lines:
            tokens = eachLine.split()
            if tokens[0] not in backup1Names:
                print (eachLine)
                if tokens[4] == "system":
                    config_portal["portal_subsystem"][portalSubsystemName]["backupId_system"] = tokens[1]
                elif tokens[4] == "site":
                    if "backupId_sites" in config_portal["portal_subsystem"][portalSubsystemName]:
                        config_portal["portal_subsystem"][portalSubsystemName]["backupId_sites"].append(tokens[1])
        print ()   
        with open(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME, 'w') as configFile:
            yaml.dump(config_portal, configFile, default_flow_style=False)
    else:
        print() 
        print("ACTION OUTPUT :Could not take portal backup. Portal namespace not provided or subsystem not installed.")


# export data for validation post migrtion
def exportDataForValidation():
    print ("Export data for validation:")
    print ("***************************")
    
    resource_dir = DATA_DIR + "/" + mgmtSubsystemName + "/resources"
    if os.path.exists(resource_dir):
        shutil.rmtree(resource_dir)
    os.makedirs(resource_dir, mode=0o755, exist_ok=True)

    for eachResource in apic_resources:
        exportResourceData(resource_dir, eachResource, apic_resources[eachResource], "", None, cloudAdminServer)


def exportResourceData(parent_dir, resourceTypeName, resourceTypeValue, params, appendDirectory, server):
    print ("\n dir : " + parent_dir +", resource type name : " + resourceTypeName + ", params : " + params)
    rdir = parent_dir + "/" + resourceTypeName
    if appendDirectory != None: rdir = rdir + "___" + appendDirectory
    
    methods = None
    if "methods" in resourceTypeValue and len(resourceTypeValue["methods"]) > 0:
        methods = resourceTypeValue["methods"]
    fields = "id,name"
    if "fields_in_list_output" in resourceTypeValue:
        fields = resourceTypeValue["fields_in_list_output"]
    list_params = params
    if "additional_params_for_list" in resourceTypeValue and resourceTypeValue["additional_params_for_list"] != "":
        list_params = list_params + " " + resourceTypeValue["additional_params_for_list"]
    
    get_params = params
    if "additional_params_for_get" in resourceTypeValue and resourceTypeValue["additional_params_for_get"] != "":
        get_params = get_params + " " + resourceTypeValue["additional_params_for_get"]

    other_params = params
    if "additional_params" in resourceTypeValue and resourceTypeValue["additional_params"] != "":
        other_params = other_params + " " + resourceTypeValue["additional_params"]
    
    exitOnError = True
    if resourceTypeName in ["gateway-extensions", "global-policy-prehooks", "global-policy-posthooks", "global-policy-errors"]: exitOnError = False

    if methods == None:
        resourceInstances = runCommand("apic " + resourceTypeName + ":list --fields " + fields + " --server " + server + " " + list_params, True)
        resourceInstances = yaml.safe_load(resourceInstances)
        if resourceInstances["total_results"] > 0:
            print ("Creating directory : " + rdir)
            os.makedirs(rdir, mode=0o755, exist_ok=True)
            runCommand("apic " + resourceTypeName + ":list --format yaml --server " + cloudAdminServer + " --output " + rdir + " " + list_params, True)
        for eachResourceInstance in resourceInstances["results"]:

            runCommand("apic " + resourceTypeName + ":get --server " + server + " --output " + rdir + " " + get_params + " " + eachResourceInstance["name"], True, 1, exitOnError)
            for eachSubResource in resourceTypeValue:
                if eachSubResource != "field_name" and eachSubResource != "methods" and eachSubResource != "additional_params_for_get" and eachSubResource != "additional_params_for_list" and eachSubResource != "fields_in_list_output":
                    addtionalDir = None
                    #if eachSubResource == "gateway-extensions" or eachSubResource == "catalog-settings":
                    addtionalDir = eachResourceInstance["name"]
                    exportResourceData(rdir, eachSubResource, resourceTypeValue[eachSubResource], params + " --" + resourceTypeValue["field_name"] + " " + eachResourceInstance["name"], addtionalDir, server)
    else:
        print ("custom method, Creating directory : " + rdir)
        os.makedirs(rdir, mode=0o755, exist_ok=True)
        for eachMethod in methods:
            if eachMethod == "get":
                runCommand("apic " + resourceTypeName + ":" + eachMethod + " --server " + server + " --output " + rdir + " " + get_params, True, 1, exitOnError)
            elif eachMethod in ["list", "list-all"]:
                runCommand("apic " + resourceTypeName + ":" + eachMethod + " --format yaml --server " + server + " --output " + rdir + " " + list_params, True, 1, exitOnError)
            else:
                runCommand("apic " + resourceTypeName + ":" + eachMethod + " --server " + server + " --output " + rdir + " " + other_params, True, 1, exitOnError)


# checks for registered gateway and portal services in management db
def getRegisteredServicesFromMgmtSubsystem():
    global gateway_portal_mapping
    if mgmtSubsystemName != None and config["management_subsystem"][mgmtSubsystemName]:
        print ("Get gateway and portal services registered with management subsystem::")
        config["management_subsystem"][mgmtSubsystemName]["registered_gateways"] = {}
        config["management_subsystem"][mgmtSubsystemName]["registered_portals"] = {}
        config["management_subsystem"][mgmtSubsystemName]["registered_analytics"] = {}
            
        orgs = runCommand("apic orgs:list --org_type=admin --fields id,name --server " + cloudAdminServer, True)
        orgs = yaml.safe_load(orgs)
        for org in orgs["results"]:
            azones = runCommand("apic availability-zones:list --fields id,name --server " + cloudAdminServer + " --org " + org["name"], True)
            azones = yaml.safe_load(azones)
            for azone in azones["results"]:
                gateways = runCommand("apic gateway-services:list --fields id,name,title,endpoint,api_endpoint_base,org_url,availability_zone_url,analytics_service_url,gateway_service_type,communication_kind --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
                gateways = yaml.safe_load(gateways)
                for gateway in gateways["results"]:
                    analytics_url = None
                    if "analytics_service_url" in gateway:
                        analytics_url = gateway["analytics_service_url"]
                    config["management_subsystem"][mgmtSubsystemName]["registered_gateways"][gateway["endpoint"]] = {
                         "id": gateway["id"],
                         "title": gateway["title"],
                         "name": gateway["name"],
                         "gateway_service_type": gateway["gateway_service_type"],
                         "endpoint": gateway["endpoint"],
                         "api_endpoint_base": gateway["api_endpoint_base"],
                         "analytics_service_url": analytics_url,
                         "org_url": gateway["org_url"],
                         "availability_zone_url": gateway["availability_zone_url"],
                         "communication_kind": gateway["communication_kind"]
                    }

                    #add gateway info to mapping file
                    gateway_portal_mapping["gateway_mapping"][gateway["name"]] = {
                        gateway["endpoint"]: "https://NEW_GATEWAY_ENDPOINT_HOST_IN_TARGET_SYSTEM",
                        gateway["api_endpoint_base"]: "https://NEW_GATEWAY_API_ENDPOINT_BASE_HOST_IN_TARGET_SYSTEM",
                        gateway["communication_kind"]: gateway["communication_kind"] #from 10.0.5.4 onwards
                    }
                
                portals = runCommand("apic portal-services:list --fields id,name,title,endpoint,web_endpoint_base,org_url,availability_zone_url,communication_kind --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
                portals = yaml.safe_load(portals)
                for portal in portals["results"]:
                    config["management_subsystem"][mgmtSubsystemName]["registered_portals"][portal["endpoint"]] = {
                        "id": portal["id"],
                        "title": portal["title"],
                        "name": portal["name"],
                        "endpoint": portal["endpoint"],
                        "web_endpoint_base": portal["web_endpoint_base"],
                        "org_url": portal["org_url"],
                        "availability_zone_url": portal["availability_zone_url"],
                        "communication_kind": portal["communication_kind"]
                    }

                    #add portal info to mapping file
                    gateway_portal_mapping["portal_mapping"][portal["name"]] = {
                        portal["endpoint"]: "https://NEW_PORTAL_ENDPOINT_HOST_IN_TARGET_SYSTEM",
                        portal["web_endpoint_base"]: "https://NEW_PORTAL_WEB_ENDPOINT_BASE_HOST_IN_TARGET_SYSTEM",
                        portal["communication_kind"]: portal["communication_kind"] 
                    }
                
                analytics = runCommand("apic analytics-services:list --fields id,ingestion_endpoint,name,title,availability_zone_url,ingestion_endpoint_tls_client_profile_url,communication_from_apim_kind --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
                analytics = yaml.safe_load(analytics)
                for eachAnalytics in analytics["results"]:
                    ingestionEP = eachAnalytics["ingestion_endpoint"]
                    if ingestionEP.endswith("/ingestion"):
                        ingestionEP = ingestionEP[0:ingestionEP.rindex("/ingestion")]

                    config["management_subsystem"][mgmtSubsystemName]["registered_analytics"][ingestionEP] = {
                        "name": eachAnalytics["name"],
                        "title": eachAnalytics["title"],
                        "availability_zone_url": eachAnalytics["availability_zone_url"],
                        "id": eachAnalytics["id"],
                        "ingestion_endpoint_tls_client_profile_url": eachAnalytics["ingestion_endpoint_tls_client_profile_url"],
                        "communication_kind": eachAnalytics["communication_from_apim_kind"]
                    }

                    #add analytics info to mapping file
                    gateway_portal_mapping["analytics_mapping"][eachAnalytics["name"]] = {
                        ingestionEP: "https://NEW_ANALYTICS_INGESTION_ENDPOINT_HOST_IN_TARGET_SYSTEM",
                        eachAnalytics["communication_from_apim_kind"]: eachAnalytics["communication_from_apim_kind"] 
                    }

        print()
        print()
        print ("ACTION OUTPUT : Creating gateway/portal mapping information in file : " + gateway_portal_mapping_filename)
        print ("Note : This mapping file can be edited and used to register new gateway/portals (register_gateway_portals_in_target.py script) when running in -silent mode.")
        with open(gateway_portal_mapping_filename, 'w') as mFile:
            mFile.write("#Mapping for gateway, analytics and portal endpoints between source and target APIC system.\n")
            mFile.write("#For each gateway/portal name in the source APIC system, the mapping between old and new endpoints of source and target APIC systems are given below.\n")
            mFile.write("#This file with actual values on left handside is GENERATED when saving the source apic system information using the script save_v10_source_configuration.py\n")
            mFile.write("#This file is used by register_gateway_portals_in_target.py when running in silent mode (-silent flag) to register the new gateways/portals.\n")
            mFile.write("#The left hand side values can also be obtained from cloud manager of the source APIC system, under topology section or using 'kubectl get ingress -n <namespace>' or 'oc get routes  -n <namespace>'.\n")
            mFile.write("#The right hand side values can can be obtained by calling 'oc get routes -n <namespace>' or 'kubectl get ingress -n <namespace>' after the target APIC system is installed.\n")
            mFile.write("#If any gateway/portal/analytics from source system are not mapped to the target, the entry for it can be removed or the generated value can be left empty or as it is on the right hand side.\n")
            mFile.write("#Left hand side values are set. Correct values must be provided on the right hand side for a successful registration of new gateways and portals.\n")
            mFile.write("#All values must begin with https://   \n")
            mFile.write("\n")
            mFile.write("#hints:\n")
            mFile.write("#gateway manager url is the gateway director url or https://NEW_GATEWAY_ENDPOINT_HOST_IN_TARGET_SYSTEM on the right side\n")
            mFile.write("#gateway url is the https://NEW_GATEWAY_API_ENDPOINT_BASE_HOST_IN_TARGET_SYSTEM on the right side\n")
            mFile.write("#portal director url is the https://NEW_PORTAL_ENDPOINT_HOST_IN_TARGET_SYSTEM on the right side\n")
            mFile.write("#portal web url is the https://NEW_PORTAL_WEB_ENDPOINT_BASE_HOST_IN_TARGET_SYSTEM on the right side\n")
            mFile.write("#ai-endpoint url is the analytics endpoint url or https://NEW_ANALYTICS_INGESTION_ENDPOINT_HOST_IN_TARGET_SYSTEM on the right side\n")
            mFile.write("#communication kind takes values external and internal_svc. If target system is cp4i, use external only on right side.\n")
            mFile.write("\n")
            yaml.dump(gateway_portal_mapping, mFile, default_flow_style=False)
        shutil.copyfile(gateway_portal_mapping_filename, DATA_TEMP_DIR + "/gateway_portal_mapping_COPY.yaml")
        print()
        print()

        #print (config)
        # save config data
        print ("Saving configuration data after adding gateway and portal sercvies")
        with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
            yaml.dump(config, configFile, default_flow_style=False)
        print()
    else:
        print("ACTION OUTPUT : Could not get registered gateway and portal services. Management namespace not provided or subsystem not installed.")

def saveTopology():
    print ("Save topology of API cluster :::")
    if mgmtSubsystemName == None:
        print("ACTION OUTPUT : Could not save topology of the cluster. Management namespace not provided or subsystem not installed.")
        return

    outputDir = DATA_DIR + "/" + mgmtSubsystemName
    runCommand("apic cloud-settings:topology --format json --server " + cloudAdminServer + " --output " + outputDir, True)
    print()



def getWebhookStatus():
    print()
    print ("Get webhook status :::")
    if mgmtSubsystemName == None:
        print("ACTION OUTPUT : Could not check webhook status. Management namespace not provided or subsystem not installed.")
        return
    
    provider_orgs = {}
    portals = {}
    gateways = {}
    orgs = runCommand("apic orgs:list --fields id,title,org_type --server " + cloudAdminServer, True)
    orgs = yaml.safe_load(orgs)
    for org in orgs["results"]:
        if org["org_type"] == "admin":
            azones = runCommand("apic availability-zones:list --fields id --server " + cloudAdminServer + " --org " + org["id"], True)
            azones = yaml.safe_load(azones)
            for azone in azones["results"]:
                gws = runCommand("apic gateway-services:list --fields id,title --server " + cloudAdminServer + " --org " + org["id"] + " --availability-zone " + azone["id"], True)
                gws = yaml.safe_load(gws)
                for gw in gws["results"]:
                    gateways[gw["id"]] = gw["title"]
                ptls = runCommand("apic portal-services:list --fields id,title --server " + cloudAdminServer + " --org " + org["id"] + " --availability-zone " + azone["id"], True)
                ptls = yaml.safe_load(ptls)
                for ptl in ptls["results"]:
                    portals[ptl["id"]] = ptl["title"]
        elif org["org_type"] == "provider":
            provider_orgs[org["id"]] = org["title"]
    
    
    cloudWebhookReport = []
    headerAdded1 = False
    cloudWebhookReport.append("ACTION OUTPUT : GATEWAY/PORTAL SERVICES WEBHOOKS (cloud level) ::")
    cloudWebhookReport.append("*****************************************************************")
    
    catalogGatewayWebhookReport = []
    headerAdded2 = False
    catalogGatewayWebhookReport.append("ACTION OUTPUT : CONFIGURED GATEWAY SERVICES (CATALOGS) WEBHOOKS ::")
    catalogGatewayWebhookReport.append("******************************************************************")
    
    catalogPortalWebhookReport = []
    headerAdded3 = False
    catalogPortalWebhookReport.append("ACTION OUTPUT : CONFIGURED PORTAL SERVICES (CATALOGS) WEBHOOKS ::")
    catalogPortalWebhookReport.append("*****************************************************************")
    
    webhooks = runCommand("apic webhooks:list --scope all --fields id,title,scope,state,portal_service_url,gateway_service_url,url --server " + cloudAdminServer, True)
    webhooks = yaml.safe_load(webhooks)
    print()
    print()

    for webhook in webhooks["results"]:
        if webhook["scope"] == "cloud":
            if not headerAdded1:
                cloudWebhookReport.append("GATEWAY/PORTAL SERVICE ID                         GATEWAY/PORTAL SERVICE TITLE                      WEBHOOK STATE                 WEBHOOK ID")
                headerAdded1 = True
                
            j = 30 - len(webhook["state"])
            if "gateway_service_url" in webhook:
                gwid = webhook["gateway_service_url"][webhook["gateway_service_url"].rindex("/") + 1:]
                if gwid in gateways:
                    i = 50 - len(gateways[gwid])
                    cloudWebhookReport.append(gwid + " (gateway)    " + gateways[gwid] + (" " * i) + webhook["state"] + (" " * j) + webhook["id"])
                else:
                    print ("Skipping webhook with id {} as the related gateway id {} not present".format(webhook["id"], gwid))
            elif "portal_service_url" in webhook:
                pid = webhook["portal_service_url"][webhook["portal_service_url"].rindex("/") + 1:]
                if pid in portals:
                    i = 50 - len(portals[pid])
                    cloudWebhookReport.append(pid + " (portal)     " + portals[pid] + (" " * i) + webhook["state"] + (" " * j) + webhook["id"])
                else:
                    print ("Skipping webhook with id {} as the related portal id {} not present".format(webhook["id"], pid))
        
        elif webhook["scope"] == "catalog":
            
            if "gateway_service_url" in webhook:
                if not headerAdded2:
                    catalogGatewayWebhookReport.append("PROVIDER ORG TITLE       CATALOG ID                              GATEWAY TITLE       WEBHOOK ID                              WEBHOOK STATE            Configured Gateway ID")
                    headerAdded2 = True
                configuredGW_ID = webhook["gateway_service_url"][webhook["gateway_service_url"].rindex("/")+1:]	
                tt1 = webhook["gateway_service_url"][webhook["gateway_service_url"].index("api/catalogs"):]
                tt1 = tt1.split("/")
                i = 25 - len(provider_orgs[tt1[2]])
                j = 20 - len(webhook["title"])
                k = 25 - len(webhook["state"])
                catalogGatewayWebhookReport.append(provider_orgs[tt1[2]] + (" " * i) + tt1[2] + "    " + webhook["title"] + (" " * j) + webhook["id"]+"    " + webhook["state"] + (" " * k) + configuredGW_ID)
            elif "portal_service_url" in webhook:
                if not headerAdded3:
                    catalogPortalWebhookReport.append("PROVIDER ORG TITLE       CATALOG ID                              PORTAL TITLE        WEBHOOK ID                              WEBHOOK STATE")
                    headerAdded3 = True
                portalid = webhook["portal_service_url"][webhook["portal_service_url"].rindex("/")+1:]	
                tt1 = webhook["url"][webhook["url"].index("api/catalogs"):]
                tt1 = tt1.split("/")
                i = 25 - len(provider_orgs[tt1[2]]) #org
                j = 40 - len(tt1[3]) #catalog
                k = 20 - len(portals[portalid])
                catalogPortalWebhookReport.append(provider_orgs[tt1[2]] + (" " * i) + tt1[3] + (" " * j) + portals[portalid] + (" " * k) + webhook["id"]+"    " + webhook["state"])
    
    cloudWebhookReport.append("")
    cloudWebhookReport.append("")
    catalogGatewayWebhookReport.append("")
    catalogGatewayWebhookReport.append("")
    catalogPortalWebhookReport.append("")
    catalogPortalWebhookReport.append("")
    
    for r1 in cloudWebhookReport:
        print(r1)
    
    for r1 in catalogGatewayWebhookReport:
        print(r1)
        
    for r1 in catalogPortalWebhookReport:
        print(r1)


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


def createProviderOrgCredentialYaml():
    global porg_credentials
    userRegistries = runCommand("apic user-registries:list --org admin --fields id,registry_type,identity_providers --server " + cloudAdminServer, True)
    userRegistries = yaml.safe_load(userRegistries)
    ur_map = {}
    for eachUr in userRegistries["results"]:
        ur_map[eachUr["id"]] = eachUr

    userRegistrySetting = None
    if os.path.exists(DATA_TEMP_DIR + "/user-registry-setting.yaml"):
        os.remove(DATA_TEMP_DIR + "/user-registry-setting.yaml")
    runCommand("apic user-registry-settings:get --server " + cloudAdminServer + " --output " + DATA_TEMP_DIR, True)
    if os.path.exists(DATA_TEMP_DIR + "/user-registry-setting.yaml"):
        text_file = open(DATA_TEMP_DIR + "/user-registry-setting.yaml", "r")
        userRegistrySetting = text_file.read()
        userRegistrySetting = yaml.safe_load(userRegistrySetting)
        text_file.close()
    else:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : user-registry-setting.yaml file NOT found. Exiting...")

    defaultUserRegistry4Provider = userRegistrySetting["provider_user_registry_default_url"]
    defaultURid = defaultUserRegistry4Provider[defaultUserRegistry4Provider.rindex("/")+1:]
    registryType = ur_map[defaultURid]["registry_type"]
    realmName = None
    if registryType != "oidc":
        realmName = "provider/" + ur_map[defaultURid]["identity_providers"][0]["name"]
    
    porgs = runCommand("apic orgs:list --org_type=provider --fields id,name --server " + cloudAdminServer, True)
    porgs = yaml.safe_load(porgs)
    for eachPOrg in porgs["results"]:
        if registryType == "oidc":
            porg_credentials["provider_org_credentials"][eachPOrg["name"]] = {
                "apiKey": "API_KEY_FROM_OIDC_AUTHENTICATION_TO_BE_CHANGED"
            }
        else:
            porg_credentials["provider_org_credentials"][eachPOrg["name"]] = {
                "username": "USERNAME_FOR_THIS_REALM_TO_BE_CHANGED",
                "password": "PASSWORD_FOR_THIS_REALM_TO_BE_CHANGED",
                "realm": realmName
            }
    #save the file at the end
    print()
    print()
    print ("ACTION OUTPUT : Saving provider org credentials in file : " + provider_org_credentials_filename)
    print ("Note : provider_org_credentials.yaml file has to be edited to fill the actual credentials. Generated yaml used by update_to_new_portals.py and update_to_new_gateways.py scripts when running in -silent mode.")
    with open(provider_org_credentials_filename, 'w') as mFile:
        mFile.write("#PROVIDER ORG CREDENTIALS FOR EACH PROVIDER ORG IN THE MANAGEMENT SUBSYSTEM.\n")
        mFile.write("#This yaml file is generated by save_v10_source_configuration.py when the source apic system configuration is saved.\n")
        mFile.write("#The yaml file is partially filled based on the value for default API manager user registry in cloud settings.\n")
        mFile.write("#The values for apiManagerHostName and username/password has to be explicitely filled by the user before using this yaml file.\n")
        mFile.write("#This yaml file is used by update_to_new_portals.py and update_to_new_gateways.py scripts when running in silent mode (-silent flag)\n")
        mFile.write("#The credentials must have admin access to the provider org.\n")
        mFile.write("#For every provider org name, the credentials are to be given below based on the authentication mechanism.\n")
        mFile.write("#If useSameCredentialsForAllProviderOrgs is set to true, you need to give credentials for only one provider org. Same will be used for other orgs.\n")
        yaml.dump(porg_credentials, mFile, default_flow_style=False)
    shutil.copyfile(provider_org_credentials_filename, DATA_TEMP_DIR + "/provider_org_credentials_COPY.yaml")
    print()
    print()

# start
def start():
    global cloudAdminServer
    print ("CHECKING IF KUBECTL/OC EXIST IN THE PATH AND HAVE ACCESS TO THE CLUSTER :")
    runKubernetesCommand("version", "default")
    print()
    
    if args.skip_namespace_validation == False:
        validateNamespaces([args.mgmt_ns, args.ptl_ns, args.gw_ns, args.a7s_ns])
    print()
    
    apicTokenFilePath = None
    if os.getenv("APIC_CONFIG_PATH") != None and os.getenv("APIC_CONFIG_PATH") != "":
        apicTokenFilePath = os.getenv("APIC_CONFIG_PATH")
        if apicTokenFilePath.endswith("/"):
            apicTokenFilePath = apicTokenFilePath + ".apiconnect/token" 
        else:
            apicTokenFilePath = apicTokenFilePath + "/.apiconnect/token" 
    else:
        apicTokenFilePath = os.path.expanduser('~') + "/.apiconnect/token" 
    
    print ("apic token file path : " + apicTokenFilePath)
    if os.path.exists(apicTokenFilePath):
        print("Deleting token file at ", apicTokenFilePath)
        os.remove(apicTokenFilePath)
    
    if args.skip_mgmt == False:
        
        print ("CHECKING IF APIC TOOLKIT IN THE PATH :: ")
        runCommand("apic version --accept-license --live-help=false")
    
        if args.sso:
            print ("Authentication using sso:")
            output = runCommand("apic cloud-settings:info --format yaml --server " + args.server, True)
            admin_endpoint = yaml.safe_load(output)["admin_endpoint"]
            print ()
            print("Please copy and paste the URL in a browser and select the authentication mechanism for SSO/OIDC based authentication.")
            print ("URL : " + admin_endpoint + "/auth/admin/sign-in/?from=TOOLKIT")
            print ("Once you get the token, copy it and enter the vaue for api key")
            print ()
            
            apiKey = args.api_key
            if args.silent:
                if apiKey == None:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Invalid api_key({}) provided for sso authentication. Exiting...".format(args.api_key))
            else:
                if apiKey == None:
                    apiKey = input("Enter the api key value after authentication using sso : ")
            runCommand("apic login --sso --context admin --server " + args.server + " --apiKey " + apiKey, False, 1)
        else:
            print ("Authentication using username/password:")
            identityProviders = runCommand("apic identity-providers:list --scope admin --fields title,realm --server " + args.server, True)
            identityProviders = yaml.safe_load(identityProviders)["results"]
            matchFound = False
            validRealms = ""
            for each in identityProviders:
                validRealms = validRealms + "      For " + each["title"] + " " * (40 - len(each["title"])) + ", realm : " + each["realm"] + "\n"
                if args.realm == each["realm"]:
                    matchFound = True
            
            if matchFound == False:
                print ("Valid realms : ")
                print(validRealms)
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : Not a valid realm for the flag, Input realm value : [{}]. Exiting...".format(args.realm))
            runCommand("apic login --server " + args.server + " --realm " + args.realm + " --username " + args.username + " --password '" + args.password + "'", False, 1)
        cloudAdminServer = args.server
    print()

    getSubsystemDetails()
    print ()

    # checks for registered gateway and portal services in management db
    if args.skip_mgmt == False:
        print ("SAVE REGISTERED PORTAL AND GATEWAY SERVICES ::")
        print ("**********************************************")
        getRegisteredServicesFromMgmtSubsystem()
    else:
        print ("ACTION OUTPUT : Skipping retrieving registered gateway and portal services. skip_mgmt or skip_management flag is set.")

    print()
    if args.skip_mgmt == False:
        print ("Generate provider_org_credentials.yaml ::")
        print ("**********************************************")
        createProviderOrgCredentialYaml()
    else:
        print ("ACTION OUTPUT : Not generating provider_org_credentials.yaml file. skip_mgmt or skip_management flag is set.")

    print()
    print()
    if args.skip_mgmt == False:
        saveTopology()
        getWebhookStatus()
    
    if args.mgmt_ns != None or args.ptl_ns != None:
        print()
        print()
        print("This script performed the following actions in the source APIC system:")
        print("**********************************************************************")
        print("1. Checked health of all the subsystems in the source APIC system.")
        print("2. Saved configuration from the source APIC system so that it can be used in the target APIC system.")
        print("3. Performed backup of management and portal subsystems and stored the backup ids.")
        print("4. Saved the registered gateway/portal/analytics services information.")
        print("5. Generated sample gateway_portal_mapping.yaml mapping file used by register_gateway_portals_in_target.py script when running in silent mode. ACTION : Target APIC system gateway/portal info has to be filled in before it can be used.")
        print("6. Generated sample provider_org_credentials.yaml file containing provider orgs credentials which will be used by other scripts when running in silent mode. ACTION : The credentials have to be filled in before the file can be used.")
        print("7. Generated reports on the status of webhooks. ACTION : Check the report.")
        print()
        print("Next steps:")
        print("1. Verify the actions from the above.")
        print("2. In the target cluster, if entitlement keys are required, create the keys and also create the namespace where APIC needs to be installed.")
        print("3. Run the create_secrets_in_target.py script in the target cluster by giving the namespace created as input.")
        print()
	
parser = argparse.ArgumentParser(description="The script is used in form factor to form factor migration. It's run against a v10 APIC cluster(source system) to collect configuration of management and\n\
portal subsystems so that the saved configuration can be used to migrate the data to the target form factor. The configuration is saved in data directory. \n\
If multiple gateway/portal subsystems are present in differnt namespaces, run the script again by pointing to the namespace.\n\n\
Prerequisites ::\n\
1. Access to the cluster (source system) using kubectl or oc.\n\
2. Python 3.x and PyYAML module need to be installed.\n\
3. Right version of apic toolkit must be in the path to run apic commands. Verify that the toolkit is able to connect to APIC system.\n\
4. Health check is performed on the subsystems.",
formatter_class=argparse.RawDescriptionHelpFormatter)


parser.add_argument("-n", "--namespace", dest = "ns", help="uses this namespace value for all subsystems if individual subsystem namespace is not provided.")
parser.add_argument("-mgmt_ns", "--management_namespace", dest = "mgmt_ns", help="namespace of the management subsystem. This has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-ptl_ns", "-portal_namespace", dest = "ptl_ns", help="namespace of the portal subsystem used for health check. If portals in multiple namespaces, use pipe(|) to separate each namespace. This value has more precedence than the common flag, -n or --namespace..")
parser.add_argument("-gw_ns", "--gateway_namespace", dest = "gw_ns", help="namespace of the gateway subsystem used for health check. If gateways in multiple namespaces, use pipe(|) to separate each namespace. This value has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-a7s_ns", "--analytics_namespace", dest = "a7s_ns", help="namespace of the analytics subsystem used for health check. If analytics in multiple namespaces, use pipe(|) to separate each namespace. This value has more precedence than the common flag, -n or --namespace.")

parser.add_argument("-u", "--username", dest = "username", help="username to login to the cloud manager UI.")
parser.add_argument("-p", "--password", dest = "password", help="password to login to the cloud manager UI.")
parser.add_argument("-s", "--server", dest = "server", help="hostname to connect to cloud manager. Use platform api hostname.")
parser.add_argument("-r", "--realm", dest = "realm", help="name of the realm the user belongs to.")
parser.add_argument("-sso", "--sso", dest = "sso", action='store_true', help="Authentication using sso/oidc.")
parser.add_argument("-api_key", "--api_key", dest = "api_key", help="api key used in sso authentication for cloud manager.")

parser.add_argument("-export_cert", "--export_cert", action='store_true', dest = "export_cert", help="Exports ingress-ca and root-ca and other secrets.")

parser.add_argument('-skip_namespace_validation', "--skip_namespace_validation",  action='store_true', dest = "skip_namespace_validation", help='Skips validation of input namespaces.')

parser.add_argument('-skip_mgmt', "--skip_management", action='store_true', dest = "skip_mgmt", help='skips management subsystem.')
parser.add_argument('-skip_ptl', "--skip_portal",  action='store_true', dest = "skip_ptl", help='skips portal subsystem.')
parser.add_argument('-skip_gw', "--skip_gateway", action='store_true', dest = "skip_gw", help='skips gateway subsystem.')
parser.add_argument('-skip_a7s', "--skip_analytics", action='store_true', dest = "skip_a7s", help='skips analytics subsystem.')

parser.add_argument('-ignore_health_check', "--ignore_health_check", action='store_true', dest = "ignore_health_check", help='ignores health check status for each subsystem and proceeds.')
parser.add_argument('-skip_mgmt_backup', "--skip_mgmt_backup", action='store_true', dest = "skip_mgmt_backup", help='skips performing backup for management subsystem.')
parser.add_argument('-skip_ptl_backup', "--skip_ptl_backup", action='store_true', dest = "skip_ptl_backup", help='skips performing backup for portal subsystem.')
parser.add_argument('-clean', "--clean", action='store_true', dest = "clean", help='delete earlier saved configuration from data directory and exit.')
parser.add_argument('-silent', "--silent", action='store_true', dest = "silent", help='Does not prompt for additinal inputs and proceeds silently.')

parser.add_argument('-export_data_for_validation', "--export_data_for_validation", action='store_true', dest = "export_data_for_validation", help='Exports data from tables that migration modifies.')
# parser.add_argument("-size", "--binsize",dest = "binsize", help="Size", type=int)
args = parser.parse_args()

print ("Start time :", time.asctime())
print ()

pwd = os.getcwd()
DATA_DIR = pwd + "/data"
DATA_TEMP_DIR = pwd + "/data/temp"

if args.clean:
    print ("Flag -clean is set. Deleting earlier saved configuration from data directory and exiting")
    print()
    
    confirmDelete = None
    if args.silent:
        confirmDelete = "yes"
    else:
        confirmDelete = input("Confirming the deletion of the data directory where all the source system configuration is saved (enter yes/no) : ")
        
    if confirmDelete != None:
        confirmDelete = confirmDelete.lower()
        if confirmDelete == "yes":
            if os.path.exists(DATA_DIR):
                shutil.rmtree(DATA_DIR)
                print ("Deleted the data directory.")
        else:
            print ("No confirmation to delete the data directory.")
            
    print()
    print ("End time :", time.asctime())
    sys.exit(0)
    
print ("Input namespace provided for all subsystems (-n or --namespace flag) : ", args.ns)
print ("Input namespace provided for management subsystem (-mgmt_ns or --management_namespace flag) : ", args.mgmt_ns)
print ("Input namespace provided for portal subsystem (-ptl_ns or --portal_namespace flag) : ", args.ptl_ns)
print ("Input namespace provided for gateway subsystem (-gw_ns or --gateway_namespace flag) : ", args.gw_ns)
print ("Input namespace provided for analytics subsystem (-a7s_ns or --analytics_namespace flag) : ", args.a7s_ns)
print ()

print ("Host name to connect to cloud manager(-s or --server flag) : ", args.server)
print ("Realm to which user belongs (-r or --realm flag) : ", args.realm)
print ("Cloud manager UI username (-u or --username flag) : ", args.username)
print ("Cloud manager UI password (-p or --password flag) : ********")
print ("SSO flag (-sso or --sso flag) : ", args.sso)
print ("api key (-api_key or --api_key flag) : ", args.api_key)
print ()

print ("Export cert (-export_cert or --export_cert flag) : ", args.export_cert)
print ()

print ("Skip checking management subsystem (-skip_mgmt or --skip_management flag) : ", args.skip_mgmt)
print ("Skip checking portal subsystem (-skip_ptl or --skip_portal flag) : ", args.skip_ptl)
print ("Skip checking gateway subsystem (-skip_gw or --skip_gateway flag) : ", args.skip_gw)
print ("Skip checking analytics subsystem (-skip_a7s or --skip_analytics flag) : ", args.skip_a7s)
print ()

print ("Ignore health check status for each subsystem (-ignore_health_check or --ignore_health_check flag) : ", args.ignore_health_check)
print ("Skip backups for management subsystem (-skip_mgmt_backup or --skip_mgmt_backup flag) : ", args.skip_mgmt_backup)
print ("Skip backups for portal subsystem (-skip_ptl_backup or --skip_ptl_backup flag) : ", args.skip_ptl_backup)
print ("Clean the data directory and exit (delete earlier saved configuration from data directory, -clean or --clean flag) : ", args.clean)
print ("silent (-silent or --silent flag) : ", args.silent)

print ("export data that is modified during migration (-export_data_for_validation or --export_data_for_validation flag) : ", args.export_data_for_validation)
print ()

forceLogPasswords = os.getenv("FORCE_LOG_PASSWORDS")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, mode=0o755, exist_ok=True)
    
if not os.path.exists(DATA_TEMP_DIR + "/temp"):
    os.makedirs(DATA_TEMP_DIR, mode=0o755, exist_ok=True)


if args.mgmt_ns == None:
    print ("Management namespace (-mgmt_ns or --management_namespace flag) not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.mgmt_ns = args.ns

if args.gw_ns == None:
    print ("Gateway namespace (-gw_ns or --gateway_namespace flag) not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.gw_ns = args.ns

#portal subsystem is optional
if args.ptl_ns == None:
    print ("Portal namespace (-ptl_ns or --portal_namespace flag) not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.ptl_ns = args.ns

#analytics subsystem is optional
if args.a7s_ns == None:
    print ("Analytics namespace (-a7s_ns or --analytics_namespace flag) not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.a7s_ns = args.ns


print ()
print ("Namespace used for management subsystem : ", args.mgmt_ns)
print ("Namespace used for portal subsystem : ", args.ptl_ns)
print ("Namespace used for gateway subsystem : ", args.gw_ns)
print ("Namespace used for analytics subsystem : ", args.a7s_ns)
print ()

if args.skip_mgmt == False and args.server == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Server(-s or --server flag) value are needed if management subsystem info need to be saved. apic toolkit is used to get info on gateway and portal services. Exiting...")
    
if args.skip_mgmt == False and args.sso == False and (args.realm == None or args.username == None or args.password == None):
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : SSO flag is false. Its username/password based authentication. Realm(-r or --realm flag) , Username(-u or --username flag) and password(-p or --password flag) is needed for using apic toolkit and get gateway and portal information. Exiting...")

ns.append(args.mgmt_ns)
ns.append(args.ptl_ns)
ns.append(args.gw_ns)
ns.append(args.a7s_ns)


# load config data if exists
if os.path.exists(DATA_DIR + "/" + CONFIG_FILE_NAME):
    print ("Configuration file exists. Loading it")
    text_file = open(DATA_DIR + "/" + CONFIG_FILE_NAME, "r")
    config1 = text_file.read()
    print("management configuration file : ", config1)
    config = yaml.safe_load(config1)
    text_file.close()
    
if os.path.exists(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME):
    print ("portal configuration file exists. Loading it")
    text_file2 = open(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME, "r")
    config2 = text_file2.read()
    print("portal configuration file : ", config2)
    config_portal = yaml.safe_load(config2)
    text_file2.close()

start()

print ()
print ("End time :", time.asctime())