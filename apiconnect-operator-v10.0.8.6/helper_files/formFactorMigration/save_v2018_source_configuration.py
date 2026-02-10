# IBM Confidential
# OCO Source Materials
#
# (C) Copyright IBM Corporation 2022
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
CONFIG_PORTAL_FILE_NAME = "config_portal.yaml"
cloudAdminServer = None
forceLogPasswords = None
mgmtSubsystemName = None

managementSubsystemsFound = 0

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

managementSecrets = ["encryptionSecret"]
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

mgmt_encryption_secret_template = {
  "apiVersion": "v1",
  "data": {
    "encryption_secret.bin": "ENCRYPTION_SECRET_VALUE"
  },
  "kind": "Secret",
  "metadata": {
    "labels": {
      "app.kubernetes.io/instance": "management",
      "app.kubernetes.io/managed-by": "ibm-apiconnect",
      "app.kubernetes.io/name": "ENCRYPTION_SECRET_NAME"
    },
    "name": "ENCRYPTION_SECRET_NAME"
  },
  "type": "Opaque"
}

ptl_encryption_secret_template = {
  "apiVersion": "v1",
  "data": {
    "encryption_secret": "ENCRYPTION_SECRET_VALUE"
  },
  "kind": "Secret",
  "metadata": {
    "labels": {
      "app.kubernetes.io/instance": "portal",
      "app.kubernetes.io/managed-by": "ibm-apiconnect",
      "app.kubernetes.io/name": "ENCRYPTION_SECRET_NAME"
    },
    "name": "ENCRYPTION_SECRET_NAME"
  },
  "type": "Opaque"
}

pvc_name = "pvc-v2018-extract"
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
        "storage": "20Gi"
      }
    },
    "storageClassName": "STORAGE_CLASS"
  }
}

extract_job_name = "v2018-mgmt-extract"
extract_job_yaml = {
  "apiVersion": "batch/v1",
  "kind": "Job",
  "metadata": {
    "name": extract_job_name,
  },
  "spec": {
    "backoffLimit": 6,
    "completions": 1,
    "parallelism": 1,
    "template": {
      "metadata": {
        "name": extract_job_name
      },
      "spec": {
        "imagePullSecrets": [
            {
                "name": "REGISTRY_SECRET"
            }
        ],
        "containers": [
          {
            "name": extract_job_name,
            "image": "docker-na.artifactory.swg-devops.com/apic-dev-docker-local/ibm-apiconnect-management-v10-upgrade@sha256:7e32b7edbb218a5a616d323432abeed7ed824833fab0334078132954eea96b9d",
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
                "name": "WORKING_DIRECTORY",
                "value": "/upgrade"
              },
              {
                "name": "LOG_DIRECTORY",
                "value": "/upgrade"
              },
              {
                "name": "CQLSH_PORT",
                "value": "9042"
              },
              {
                "name": "DEBUG",
                "value": "v10-upgrade:*"
              },
              {
                "name": "SLEEP_BEFORE_FOR_SECONDS",
                "value": "300"
              }
            ],
            "volumeMounts": [
              {
                "mountPath": "/upgrade",
                "name": "v2018-extract-volume"
              },
              {
                "mountPath": "/etc/cassandra/certs",
                "name": "db-client-velox-certs-volume",
                "readOnly": True
              }
            ]
          }
        ],
        #"nodeSelector": {
        #  "kubernetes.io/hostname": "NODE_NAME"
        #},
        "restartPolicy": "OnFailure",
        "volumes": [
          {
            "name": "v2018-extract-volume",
            "persistentVolumeClaim": {
              "claimName": pvc_name
            }
          },
          {
            "name": "db-client-velox-certs-volume",
            "secret": {
              "defaultMode": 420,
              "secretName": "DB_CLIENT_VELOX_CERTS"
            }
          }
        ]
      }
    }
  }
}

downloadUsingNginxImage = False
deployNginxName = "n-v2018-mgmt-extract-download"
deployNginx_yaml = {
  "apiVersion": "apps/v1",
  "kind": "Deployment",
  "metadata": {
    "name": deployNginxName
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
                "name": "v2018-extract-volume"
              }
            ]
          }
        ],
        "volumes": [
          {
            "name": "v2018-extract-volume",
            "persistentVolumeClaim": {
              "claimName": pvc_name
            }
          }
        ]
      }
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
    global managementSubsystemsFound
    print ("Loading apiconnect-up.yml file to read database backup properties for management/portal subsystems")
    apicupyamlfile = open("apiconnect-up.yml", "r")
    apicupyaml = apicupyamlfile.read()
    apicupyaml = yaml.safe_load(apicupyaml)
    apicupyamlSubsystems = apicupyaml["spec"]["subsystems"]
    apicupyamlfile.close()

    subsystemsList = runCommand("apicup subsys list")
    if subsystemsList == None and subsystemsList == "":
        print ("ACTION OUTPUT : No API Connect subsystems are present in the project. Check the project and try again.")
        sys.exit(1)
    
    subsystemsLinesArray = subsystemsList.splitlines()
    k = 0
    for eachSubsystem in subsystemsLinesArray:
        if k == 0:
            k = k + 1
            continue
        subsystemType = None
        subsystemName = eachSubsystem[0:eachSubsystem.index(" ")]

        if "ManagementSubsystem" in eachSubsystem:
            subsystemType = "Management subsystem"
            if args.skip_mgmt == True:
                print ("ACTION OUTPUT : Skipping management subsystem because skip_mgmt flag is set in the input.")
                continue
            if managementSubsystemsFound > 0:
                print()
                print()
                print ("Found another management subsystem with name " + subsystemName)
                print ("Type yes to skip. Skip only if you are NOT on the right virtual machine/node for this subsystem where you have access to the subsystem pods and configuration.")
                skip = input("Skip this management subsystem, type yes to skip : ")
                if skip != None: skip = skip.strip()
                skip = skip.lower()
                if (skip == "yes"):
                    continue

        elif "PortalSubsystem" in eachSubsystem:
            subsystemType = "Portal subsystem"
            if args.skip_ptl == True:
                print ("ACTION OUTPUT : Skipping portal subsystem because skip_ptl flag is set in the input.")
                continue

            print()
            print ("Found portal subsystem with name " + subsystemName)
            print ("Skip this portal subsystem only if you are NOT on the right virtual machine/node for this subsystem where you have access to the subsystem pods and configuration.")
            print ("If you are having multiple portal subsystems, you need to run the script for each subsystem on one of the nodes of that subsystem. While running on a subsystem node, skip the other subsystem names.")
            skip = input("Skip this portal subsystem, type yes to skip : ")
            if skip != None: skip = skip.strip()
            skip = skip.lower()
            if (skip == "yes"):
                continue
        elif "GatewaySubsystem" in eachSubsystem:
            subsystemType = "Gateway subsystem"
            if  args.skip_gw == True:
                print ("ACTION OUTPUT : Skipping gateway subsystem because skip_gw flag is set in the input.")
                continue
        elif "AnalyticsSubsystem" in eachSubsystem:
            subsystemType = "Analytics subsystem"
            if args.skip_a7s == True:
                print ("ACTION OUTPUT : Skipping analytics subsystem because skip_a7s flag is set in the input.")
                continue

        if args.ocp:
            if subsystemType == "Management subsystem":
                runKubernetesCommand("project " + args.mgmt_ns, None)
            elif subsystemType == "Portal subsystem":
                runKubernetesCommand("project " + args.ptl_ns, None)
            elif subsystemType == "Analytics subsystem":
                runKubernetesCommand("project " + args.a7s_ns, None)
            elif subsystemType == "Gateway subsystem":
                runKubernetesCommand("project " + args.gw_ns, None)

        healthCheckOutput = runCommand("apicup subsys health-check " + subsystemName, False, 10, False)
        print ("Health check output for " + subsystemType + " : [[" + healthCheckOutput + "]]")
        if healthCheckOutput != "":
            if not args.ignore_health_check:
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : Health check failed for {} with name {}. Health check output : {}".format(subsystemType, subsystemName, healthCheckOutput))
        
        print ("ACTION OUTPUT : " + subsystemType + " is healthy.")
        print()
        if not os.path.exists(DATA_DIR + "/" + subsystemName ):
            os.makedirs(DATA_DIR + "/" + subsystemName , mode=0o755, exist_ok=True)

        if subsystemType == "Management subsystem":
            managementSubsystemsFound = managementSubsystemsFound + 1
            mgmtSubsystemName = subsystemName
            apicupyamlMGMTSubsys = None
            for each in apicupyamlSubsystems:
                if each["kind"] == "apic.ibm.com/ManagementSubsystem"  and each["metadata"]["name"] == subsystemName:
                    apicupyamlMGMTSubsys = each
                    break
            
            if args.skip_mgmt_backup == False:
                print ("Validating database backup configuration for management subsystem")
                if "cassandra-backup-protocol" not in apicupyamlMGMTSubsys["spec"]["settings"] or "cassandra-backup-host" not in apicupyamlMGMTSubsys["spec"]["settings"] or "cassandra-backup-path" not in apicupyamlMGMTSubsys["spec"]["settings"] or "cassandra-backup-auth-user" not in apicupyamlMGMTSubsys["spec"]["settings"] or "cassandra-backup-auth-pass" not in apicupyamlMGMTSubsys["spec"]["settings"]:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Management subsystem ({}) validation failed. Database backup not configured.  Exiting...".format(subsystemName))
                
            d1 = {}
            if subsystemName in config["management_subsystem"]:
                d1 = config["management_subsystem"][subsystemName]

            productVersion = getProductVersionFromAPIMDeployment()
            print ("ACTION OUTPUT : product version is " + productVersion)
            d1["versionReconciled"] = productVersion
            d1["name"] = subsystemName            
            
            mgmtEncryptionSecretName = subsystemName + "-enc-key"
            d1["encryptionSecret"] = {
                "secretName": mgmtEncryptionSecretName
            }
            d1["databaseBackup"] = {
                "protocol": apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-protocol"],
                "host": apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-host"],
                "path": apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-path"],
                "credentials": "management-backup-secret"
            }
            if "cassandra-backup-port" in apicupyamlMGMTSubsys["spec"]["settings"]:
                d1["databaseBackup"]["port"] = apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-port"]

            if "cassandra-backup-schedule" in apicupyamlMGMTSubsys["spec"]["settings"]:
                d1["databaseBackup"]["schedule"] = apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-schedule"]
            
            config["management_subsystem"][subsystemName] = d1

            mgmtBackupSecret = {
                "apiVersion": "v1",
                "data": {
                    "password": "password_base64_encoded",
                    "username": "username_base64_encoded"
                },
                "kind": "Secret",
                "metadata": {
                    "name": "management-backup-secret"
                },
                "type": "Opaque"
            }

            usernameBase64Encoded = base64.b64encode(apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-auth-user"].encode('ascii'))
            usernameBase64Encoded = usernameBase64Encoded.decode("ascii")

            if apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-protocol"] == "objstore":
                del mgmtBackupSecret["data"]["password"]
                del mgmtBackupSecret["data"]["username"]
                mgmtBackupSecret["data"]["key"] = usernameBase64Encoded
                mgmtBackupSecret["data"]["keysecret"] = apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-auth-pass"]
            else:
                mgmtBackupSecret["data"]["username"] = usernameBase64Encoded
                mgmtBackupSecret["data"]["password"] = apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-auth-pass"]

            if apicupyamlMGMTSubsys["spec"]["settings"]["cassandra-backup-protocol"] == "objstore":
                print ("s3 backup being used for management backup.")
                s3provider = input("Enter the s3 provider being used (value must be one of ibm, aws, custom)  :  ")
                s3provider = s3provider.lower()
                if s3provider not in ["aws", "ibm", "custom"]:
                    sys.exit("ERROR : Invalid s3 provider value ({}) given. Supported values are aws, ibm and custom".format(s3provider))
                d1["databaseBackup"]["s3provider"] = s3provider
                if d1["databaseBackup"]["s3provider"] == "custom":
                    print ("Custom s3 provider being used. You will need to set additional properties like backupCerts and backups3URIStyle. Refer API Connect  knowledge center for more details.")

            with open(DATA_DIR + "/" + subsystemName + "/" + "management-backup-secret.yaml", 'w') as backupSecret:
                yaml.dump(mgmtBackupSecret, backupSecret, default_flow_style=False)

            mgmtSubsysPropertiesSecret = apicupyamlMGMTSubsys["spec"]["SubsystemProperties"]["secret-name"]
            filename1 = mgmtSubsysPropertiesSecret + "-" + args.mgmt_ns + "-secrets.yml"
            mgmtSubsysSecretsfile = open(filename1, "r")
            mgmtSecrets = mgmtSubsysSecretsfile.read()
            mgmtSecrets = yaml.safe_load(mgmtSecrets)
            mgmtSubsysSecretsfile.close()
            
            mgmt_encryption_secret_template["data"]["encryption_secret.bin"] = mgmtSecrets["data"]["encryption-secret.bin"]
            mgmt_encryption_secret_template["metadata"]["name"] = mgmtEncryptionSecretName
            mgmt_encryption_secret_template["metadata"]["labels"]["app.kubernetes.io/name"] = mgmtEncryptionSecretName
            with open(DATA_DIR + "/" + subsystemName + "/" + mgmtEncryptionSecretName + ".yaml", 'w') as encrSecret:
                yaml.dump(mgmt_encryption_secret_template, encrSecret, default_flow_style=False)
            
            if args.export_cert:
                rootCACert = runCommand("apicup certs get " + subsystemName + " root-ca --type cert", True)
                if rootCACert != None: rootCACert = rootCACert.strip()
                rootCACertBase64Encoded = base64.b64encode(rootCACert.encode('ascii'))
                rootCACertBase64Encoded = rootCACertBase64Encoded.decode("ascii")

                rootCAKey = runCommand("apicup certs get " + subsystemName + " root-ca --type key", True)
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
                rootcaFileName = DATA_DIR + "/" + subsystemName + "/root-ca_secret.yaml"
                with open(rootcaFileName, 'w') as f1:
                    yaml.dump(rootCASecret, f1, default_flow_style=False)
                print("root-ca secret location : ", rootcaFileName)
                print()

                ingressCACert = runCommand("apicup certs get " + subsystemName + " ingress-ca --type cert", True)
                if ingressCACert != None: ingressCACert = ingressCACert.strip()
                ingressCACertBase64Encoded = base64.b64encode(ingressCACert.encode('ascii'))
                ingressCACertBase64Encoded = ingressCACertBase64Encoded.decode("ascii")

                ingressCAKey = runCommand("apicup certs get " + subsystemName + " ingress-ca --type key", True)
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
                ingressCAFileName = DATA_DIR + "/" + subsystemName + "/ingress-ca_secret.yaml"
                with open(ingressCAFileName, 'w') as f1:
                    yaml.dump(ingressCASecret, f1, default_flow_style=False)
                print("ingress-ca secret location : ", ingressCAFileName)

                config["management_subsystem"][subsystemName]["root_ca_secret"] = "root-ca_cert.yaml"
                config["management_subsystem"][subsystemName]["ingress_ca_secret"] = "ingress-ca_secret.yaml"
                print()
            
            print()
            if args.skip_mgmt_backup == False:
                print ("CREATE MANAGEMENT BACKUP ::")
                print ("***************************")
                createManagementBackup()
            else:
                print ("ACTION OUTPUT : Skipping management backup. skip_mgmt_backup flag is set.")

            print()
            if args.export_data_for_validation == True:
                exportDataForValidation ()
                config["management_subsystem"][subsystemName]["export_data_for_validation"] = True
                config["management_subsystem"][subsystemName]["export_data_orgs_list"] = []

        if subsystemType == "Portal subsystem":
            apicupyamlPTLSubsys = None
            for each in apicupyamlSubsystems:
                if each["kind"] == "apic.ibm.com/PortalSubsystem" and each["metadata"]["name"] == subsystemName:
                    apicupyamlPTLSubsys = each
                    break
            
            if args.skip_ptl_backup == False:
                print ("Validating database backup configuration for portal subsystem")
                if "site-backup-protocol" not in apicupyamlPTLSubsys["spec"]["settings"] or "site-backup-host" not in apicupyamlPTLSubsys["spec"]["settings"] or "site-backup-path" not in apicupyamlPTLSubsys["spec"]["settings"] or "site-backup-auth-user" not in apicupyamlPTLSubsys["spec"]["settings"] or "site-backup-auth-pass" not in apicupyamlPTLSubsys["spec"]["settings"]:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Portal subsystem validation failed. Database backup not configured.  Exiting...")
              

            d1 = {}
            if subsystemName in config_portal["portal_subsystem"]:
                d1 = config_portal["portal_subsystem"][subsystemName]

            ptlEncryptionSecretName = subsystemName + "-enc-key"
            d1["encryptionSecret"] = {
                "secretName": ptlEncryptionSecretName
            }
            d1["name"] = subsystemName

            d1["portalBackup"] = {
                "protocol": apicupyamlPTLSubsys["spec"]["settings"]["site-backup-protocol"],
                "host": apicupyamlPTLSubsys["spec"]["settings"]["site-backup-host"],
                "path": apicupyamlPTLSubsys["spec"]["settings"]["site-backup-path"],
                "credentials": "portal-backup-secret"
            }
            if "site-backup-port" in apicupyamlPTLSubsys["spec"]["settings"]:
                d1["portalBackup"]["port"] = apicupyamlPTLSubsys["spec"]["settings"]["site-backup-port"]
            
            if "site-backup-schedule" in apicupyamlPTLSubsys["spec"]["settings"]:
                d1["portalBackup"]["schedule"] = apicupyamlPTLSubsys["spec"]["settings"]["site-backup-schedule"]

            config_portal["portal_subsystem"][subsystemName] = d1

            ptlBackupSecret = {
                "apiVersion": "v1",
                "data": {
                    "password": "password_base64_encoded",
                    "username": "username_base64_encoded"
                },
                "kind": "Secret",
                "metadata": {
                    "name": "portal-backup-secret"
                },
                "type": "Opaque"
            }

            if "site-backup-auth-pass" in apicupyamlPTLSubsys["spec"]["settings"]:
                ptlBackupSecret["data"]["password"] = apicupyamlPTLSubsys["spec"]["settings"]["site-backup-auth-pass"]
            if "site-backup-auth-user" in apicupyamlPTLSubsys["spec"]["settings"]:
                usernameBase64Encoded = base64.b64encode(apicupyamlPTLSubsys["spec"]["settings"]["site-backup-auth-user"].encode('ascii'))
                usernameBase64Encoded = usernameBase64Encoded.decode("ascii")
                ptlBackupSecret["data"]["username"] = usernameBase64Encoded
            
            if ptlBackupSecret["data"]["username"] == "username_base64_encoded"  or ptlBackupSecret["data"]["password"] == "password_base64_encoded":
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : Could not get username and password for portal backups configuration. Exiting...")

            with open(DATA_DIR + "/" + subsystemName + "/" + "portal-backup-secret.yaml", 'w') as backupSecret:
                yaml.dump(ptlBackupSecret, backupSecret, default_flow_style=False)

            portalWWWPods = runKubernetesCommand("get pods --no-headers | grep www", args.ptl_ns)
            portalWWWPodsList = portalWWWPods.splitlines()
            for eachPortalWWWPod in portalWWWPodsList:
                portalWWWPod = eachPortalWWWPod[0:eachPortalWWWPod.index(" ")]
                portalEncryptionSecret = runKubernetesCommand("exec -it " + portalWWWPod + " -c admin -- cat /var/devportal/store/enckey" , args.ptl_ns)

                portalEncryptionSecret = base64.b64encode(portalEncryptionSecret.encode('ascii'))
                portalEncryptionSecret = portalEncryptionSecret.decode("ascii")
                ptl_encryption_secret_template["data"]["encryption_secret"] = portalEncryptionSecret
                
                ptl_encryption_secret_template["metadata"]["name"] = ptlEncryptionSecretName
                ptl_encryption_secret_template["metadata"]["labels"]["app.kubernetes.io/name"] = ptlEncryptionSecretName
                with open(DATA_DIR + "/" + subsystemName + "/" + ptlEncryptionSecretName + ".yaml", 'w') as encrSecret:
                    yaml.dump(ptl_encryption_secret_template, encrSecret, default_flow_style=False)
                break

            print()	
            if args.skip_ptl_backup == False:
                print ("CREATE PORTAL BACKUP ::")
                print ("***********************")
                createPortalBackup(subsystemName)
            else:
                print ("ACTION OUTPUT : Skipping portal backup. skip_ptl_backup flag is set.")


        print ("ACTION OUTPUT : Saving configuration data for {} with name, {}".format(subsystemType, subsystemName))
        if subsystemType == "Management subsystem" or subsystemType == "Gateway subsystem" or subsystemType == "Analytics subsystem":
            with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
                yaml.dump(config, configFile,  default_flow_style=False)
        else:
            with open(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME, 'w') as configFile2:
                yaml.dump(config_portal, configFile2, default_flow_style=False)
        print()
        print()
            


def getProductVersionFromAPIMDeployment():
    deployments = runKubernetesCommand("get deployment", args.mgmt_ns)
    deploymentList = deployments.splitlines()
    for eachDeploy in deploymentList:
        if "-apim-v2" in eachDeploy:
            apimDeploymentName = eachDeploy[0:eachDeploy.index(" ")]
            apimDeploy = runKubernetesCommand("get deployment " + apimDeploymentName + " -o json" , args.mgmt_ns, True)
            apimDeploy = yaml.safe_load(apimDeploy)
            return apimDeploy["metadata"]["annotations"]["productVersion"]
    return None

# management backup
def createManagementBackup():
    hostWhereCassandraPodRunning = []
    mgmtCassandraPods = runKubernetesCommand("get pods --no-headers -o wide | grep Running | grep apiconnect-cc-", args.mgmt_ns)
    mgmtCassandraPodsList = mgmtCassandraPods.splitlines()
    for eachPod in mgmtCassandraPodsList:
        if "backup" not in eachPod:
            d = mgmtCassandraPods.split()
            hostWhereCassandraPodRunning.append(d[6])
    print("ACTION OUTPUT : hostnames where cassandra is running : ", hostWhereCassandraPodRunning)
    if len(hostWhereCassandraPodRunning) == 0:
        sys.exit("ERROR : No running cassandra pods. Check the management subsystem health.")
    
    #pvsList = runKubernetesCommand("get pv -ojsonpath='{.items[*].metadata.name}'", args.mgmt_ns, True)
    #pvsList = pvsList.strip("\n").split()

    #cassandraHost = None
    #selectedAvaialblePV = None
    #for eachHostOfCassandra in hostWhereCassandraPodRunning:
    #    for eachPVName in pvsList:
    #        pvDetails = runKubernetesCommand("get pv " + eachPVName + " -o yaml", args.mgmt_ns, True)
    #        pvDetails = yaml.safe_load(pvDetails)
    #        if pvDetails["status"]["phase"] == "Available":
    #            selectedAvaialblePV = eachPVName
    #            cassandraHost = eachHostOfCassandra
    #            break
    #    if selectedAvaialblePV != None:
    #        break
    #if selectedAvaialblePV == None:
    #    sys.exit("No persistence volume is available which is needed to run extract job. Check if any PVC can be deleted and try again.")
    
    #print ("Cassandra Host : ", cassandraHost)
    #print ("Selected available persistence volume : ", selectedAvaialblePV)

    dbServiceHost = None
    pods = runKubernetesCommand("get pods --no-headers", args.mgmt_ns, True)
    if pods != None and pods.lower().startswith("error") == False:
        pods = pods.splitlines()
        for eachPod in pods:
            if "-apiconnect-cc" in eachPod:
                dbServiceHost = eachPod[0:eachPod.index("-")] + "-apiconnect-cc"
                break
    print ("ACTION OUTPUT : DB_SERVICE_HOST: " + dbServiceHost)
        
    dbClientVeloxCerts = None
    secrets = runKubernetesCommand("get secret", args.mgmt_ns, True)
    if secrets != None and secrets.lower().startswith("error") == False:
        secrets = secrets.splitlines()
        for eachSecret in secrets:
            if "db-client-velox-certs-" in eachSecret:
                dbClientVeloxCerts = eachSecret[0:eachSecret.index(" ")]
                break
    print ("ACTION OUTPUT : dbClientVeloxCerts : " + dbClientVeloxCerts)

    #check if extract job exists and delete it
    extractJob = runKubernetesCommand("get job " + extract_job_name + " --no-headers", args.mgmt_ns, False, 0, False)
    if extractJob != None and extractJob.lower().startswith(extract_job_name):
        runKubernetesCommand("delete job " + extract_job_name, args.mgmt_ns, False)
        time.sleep(30)
    else:
        print ("ACTION OUTPUT : " + extract_job_name + " job not found. Will create extract job")

    #check if deployment for downloading csv extract exists and delete it
    downloadCSVDeploy = runKubernetesCommand("get deploy " + deployNginxName + " --no-headers", args.mgmt_ns, False, 0, False)
    if downloadCSVDeploy != None and downloadCSVDeploy.lower().startswith(deployNginxName):
        runKubernetesCommand("delete deploy " + deployNginxName, args.mgmt_ns, False)
        time.sleep(40)
    else:
        print ("ACTION OUTPUT : " + deployNginxName + " used to download csv not found. Will create if needed.")

    
    pvc = runKubernetesCommand("get pvc " + pvc_name + " --no-headers", args.mgmt_ns, False, 0, False)
    if pvc != None and pvc.lower().startswith(pvc_name):
        runKubernetesCommand("delete pvc " + pvc_name, args.mgmt_ns, False)
        time.sleep(30)
    else:
        print ("ACTION OUTPUT : " + pvc_name + " pvc not found. Will create new pvc")

    #create pvc
    pvc_template["metadata"]["name"] = pvc_name
    pvc_template["spec"]["storageClassName"] = args.storage_class
    if args.extract_storage_size != None: 
        pvc_template["spec"]["resources"]["requests"]["storage"] = args.extract_storage_size + "Gi"
    #pvc_template["spec"]["volumeName"] = selectedAvaialblePV
    with open(DATA_TEMP_DIR + "/pvc_extract.yaml", 'w') as pvcFile:
        yaml.dump(pvc_template, pvcFile, default_flow_style=False)
    runKubernetesCommand("apply -f " + DATA_TEMP_DIR + "/pvc_extract.yaml", args.mgmt_ns)
    time.sleep(30)

    extracted_data = DATA_DIR + "/" + mgmtSubsystemName + "/extracted_data"
    if not os.path.exists(extracted_data):
        os.makedirs(extracted_data, mode=0o755, exist_ok=True)

    #create extract job
    if args.registry_secret == None:
        del extract_job_yaml["spec"]["template"]["spec"]["imagePullSecrets"]
    else:
        extract_job_yaml["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"] = args.registry_secret
    #extract_job_yaml["spec"]["template"]["spec"]["nodeSelector"]["kubernetes.io/hostname"] = cassandraHost
    for eachVol in extract_job_yaml["spec"]["template"]["spec"]["volumes"]:
        if eachVol["name"] == "db-client-velox-certs-volume":
            eachVol["secret"]["secretName"] = dbClientVeloxCerts
    
    cassandra_hostname_env = {
        "name": "CQLSH_HOST",
        "value": dbServiceHost
    }
    extract_job_yaml["spec"]["template"]["spec"]["containers"][0]["env"].append(cassandra_hostname_env)

    if args.skip_csv_download == False and downloadUsingNginxImage == False:
        env1 = {
            "name": "FROM_FFM_WAIT_FOR_CSV_TASK_COMPLETION",
            "value": "true"
        }
        env2 = {
            "name": "FROM_FFM_CSV_TASK_LOOP_COUNT",
            "value": "60"
        }
        extract_job_yaml["spec"]["template"]["spec"]["containers"][0]["env"].append(env1)
        extract_job_yaml["spec"]["template"]["spec"]["containers"][0]["env"].append(env2)

    if args.extract_image != None:
        extract_job_yaml["spec"]["template"]["spec"]["containers"][0]["image"] = args.extract_image

    with open(DATA_TEMP_DIR + "/extract_job.yaml", 'w') as f3:
        yaml.dump(extract_job_yaml, f3, default_flow_style=False)
    runKubernetesCommand("apply -f " + DATA_TEMP_DIR + "/extract_job.yaml", args.mgmt_ns)
    time.sleep(60)

    if args.skip_csv_download == False:
        neededPod = None
        extractDownloadDeploy = None
        if downloadUsingNginxImage:
            checkForExtractJobCompletion()
            
            #download the extracted csv and copy to data folder
            if args.nginx_image != None:
                deployNginx_yaml["spec"]["template"]["spec"]["containers"][0]["image"] = args.nginx_image
                if args.registry_secret == None:
                    del deployNginx_yaml["spec"]["template"]["spec"]["imagePullSecrets"]
                else:
                    deployNginx_yaml["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"] = args.registry_secret
            else:
                del deployNginx_yaml["spec"]["template"]["spec"]["imagePullSecrets"]

            extractDownloadDeploy = DATA_TEMP_DIR + "/extract_download_deploy.yaml"
            with open(extractDownloadDeploy, 'w') as f3:
                yaml.dump(deployNginx_yaml, f3, default_flow_style=False)
            runKubernetesCommand("apply -f " + extractDownloadDeploy, args.mgmt_ns)
            neededPod = deployNginxName
        else:
            #download csv using extract pod only
            neededPod = extract_job_name
            print()
        
        time.sleep(60)
        foundPod = False
        pods = runKubernetesCommand("get pods --no-headers", args.mgmt_ns, True)
        if pods != None and pods.lower().startswith("error") == False:
            pods = pods.splitlines()
            for eachPod in pods:
                if "Running" in eachPod and neededPod in eachPod:
                    neededPod = eachPod[0:eachPod.index(" ")]
                    foundPod = True
                    break
        
        if foundPod == False:
            sys.exit("Pod to download csv from pvc is not ready. The pod name is not available.")
        
        print ("Use this pod to download the extracted csv: ", neededPod)
        
        if downloadUsingNginxImage == False:
            if os.path.exists(DATA_TEMP_DIR + "/EXTRACT.COMPLETE"):
                os.remove(DATA_TEMP_DIR + "/EXTRACT.COMPLETE")
            cpCommand = "cp " + args.mgmt_ns + "/" + neededPod + ":/upgrade/logs/EXTRACT.COMPLETE " + DATA_TEMP_DIR + "/EXTRACT.COMPLETE"
            a1 = runKubernetesCommand(cpCommand, None, False, 0, False)
            c1 = 0
            while os.path.exists(DATA_TEMP_DIR + "/EXTRACT.COMPLETE") == False:
                print ("Waiting for extract completion :", time.asctime())
                time.sleep(60)
                a1 = runKubernetesCommand(cpCommand, None, False, 0, False)
                c1 = c1 + 1
                if c1 > 180:
                    print("Exiting loop as waited for 3 hours for extract to complete")
                    break;
            if os.path.exists(DATA_TEMP_DIR + "/EXTRACT.COMPLETE") == False:
                sys.exit("ERROR : Looks like extract of data from v2018 did not complete or there was an error in checking the extract complete condition.")

        runKubernetesCommand("cp " + args.mgmt_ns + "/" + neededPod + ":/upgrade " + extracted_data, None, False, 50, True)
        print ("ACTION OUTPUT : Downloaded extracted data from management subsystem and saved in directory, ", extracted_data)

        time.sleep(20)
        if downloadUsingNginxImage:
            runKubernetesCommand("delete -f " + extractDownloadDeploy, args.mgmt_ns)
        else:   
            file_name = DATA_TEMP_DIR + "/csvDownloadComplete.txt"
            f = open(file_name, 'a')  # open file in write mode
            f.write('csv download complete')
            f.close()
            runKubernetesCommand("cp " + file_name + " " + args.mgmt_ns + "/" + neededPod + ":/upgrade/logs/csvDownloadComplete.txt", None, False, 50, True)
            time.sleep(30)
            checkForExtractJobCompletion()

    else:
        checkForExtractJobCompletion()
        print ()
        print ()
        print ("skip_csv_download flag is set.")
        print ("ACTION OUTPUT ::")
        print ("Not downloading extracted csv to the machine where script is run. The csv has to be explicitely downloaded from the pvc.")
        print ("The extracted contents MUST be downloaded to dir path : ", extracted_data)
        print("If API Connect is on VMWare, you can describe the pv to get the directory path and copy the contents from there.")
        print ("If API Connect is not on VMWare, attach the pvc to a pod using mount path /upgrade and download the contents. PVC name : ", pvc_name)
        print ()
        print ("IMPORTANT : Directory structure after csv download, check it and validate :: ")
        print ("apim database csv contents in : ", extracted_data + "/data/apim")
        print ("lur database csv contents in : ", extracted_data + "/data/lur")
        print ("Logs present in  : ", extracted_data + "/logs")
        print ()
        confirm = input("Read the above ACTION OUTPUT and confirm that the extracted data will be downloaded : ")
        print ("Confirm status : ", confirm)
        print ()
        print ()
    print ("ACTION OUTPUT : Management subsystem backup complete.")


def checkForExtractJobCompletion():
    while isExtractJobCompleted() == False:
        print ("Waiting for extract job({}) to be completed.".format(extract_job_name))
        time.sleep(60)
    extractJob = runKubernetesCommand("get job " + extract_job_name + " -o yaml", args.mgmt_ns, True, 1, False)
    extractJob = yaml.safe_load(extractJob)
    if "status" not in extractJob or "succeeded" not in extractJob["status"] or extractJob["status"]["succeeded"] != 1:
        sys.exit("ERROR : Extract job failed. Could not retrieve data from management subsystem.")
    print ("ACTION OUTPUT : Extracted data from management subsystem and available in PVC.")

def isExtractJobCompleted():
    extractJob = runKubernetesCommand("get job " + extract_job_name + " --no-headers", args.mgmt_ns, False, 15, False)
    if extractJob != None and extractJob.lower().startswith(extract_job_name):
        extractJob = runKubernetesCommand("get job " + extract_job_name + " -o yaml", args.mgmt_ns, True, 15, False)
        extractJob = yaml.safe_load(extractJob)
        if "conditions" in extractJob["status"]:
            for eachCondition in extractJob["status"]["conditions"]:
                if (eachCondition["type"] == "Complete" and eachCondition["status"] == "True"):
                    return True
    else:
        sys.exit("Extract job not found. Exiting.")
    return False
    


# portal backup
def createPortalBackup(subsystemName):
    initialPortalBackups = []
    print("Get existing portal backup:")
    portalBackups = runCommand("apicup subsys exec " + subsystemName + " list-backups remote", False)
    if portalBackups != None and portalBackups != "" :
        portalBackups = portalBackups.splitlines()
        for eachBackup in portalBackups:
            eachBackup = eachBackup.strip()
            initialPortalBackups.append(eachBackup)

    print("creating portal backup:")
    runCommand("apicup subsys exec " + subsystemName + " backup", False)
    time.sleep(120)
    portalBackups = runCommand("apicup subsys exec " + subsystemName + " list-backups remote", False)
    print ("ACTION OUTPUT : Portal subsystem backup complete.")
    config_portal["portal_subsystem"][subsystemName]["backupId_sites"] = []
    if portalBackups != None and portalBackups != "" :
        portalBackups = portalBackups.splitlines()
        for eachBackup in portalBackups:
            eachBackup = eachBackup.strip()
            if eachBackup not in initialPortalBackups:
                if eachBackup.startswith("_portal_system_backup"):
                    config_portal["portal_subsystem"][subsystemName]["backupId_system"] = eachBackup
                else:
                    if "backupId_sites" in config_portal["portal_subsystem"][subsystemName]:
                        config_portal["portal_subsystem"][subsystemName]["backupId_sites"].append(eachBackup)
    print ("ACTION OUTPUT : Saved backup file names of Portal subsystem.")
                        

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
                gateways = runCommand("apic gateway-services:list --fields id,name,title,endpoint,api_endpoint_base,org_url,availability_zone_url,analytics_service_url,gateway_service_type --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
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
                         "availability_zone_url": gateway["availability_zone_url"]
                    }

                    #add gateway info to mapping file
                    gateway_portal_mapping["gateway_mapping"][gateway["name"]] = {
                        gateway["endpoint"]: "https://NEW_GATEWAY_ENDPOINT_HOST_IN_TARGET_SYSTEM",
                        gateway["api_endpoint_base"]: "https://NEW_GATEWAY_API_ENDPOINT_BASE_HOST_IN_TARGET_SYSTEM"
                    }
                
                portals = runCommand("apic portal-services:list --fields id,name,title,endpoint,web_endpoint_base,org_url,availability_zone_url --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
                portals = yaml.safe_load(portals)
                for portal in portals["results"]:
                    config["management_subsystem"][mgmtSubsystemName]["registered_portals"][portal["endpoint"]] = {
                        "id": portal["id"],
                        "title": portal["title"],
                        "name": portal["name"],
                        "endpoint": portal["endpoint"],
                        "web_endpoint_base": portal["web_endpoint_base"],
                        "org_url": portal["org_url"],
                        "availability_zone_url": portal["availability_zone_url"]
                    }

                    #add portal info to mapping file
                    gateway_portal_mapping["portal_mapping"][portal["name"]] = {
                        portal["endpoint"]: "https://NEW_PORTAL_ENDPOINT_HOST_IN_TARGET_SYSTEM",
                        portal["web_endpoint_base"]: "https://NEW_PORTAL_WEB_ENDPOINT_BASE_HOST_IN_TARGET_SYSTEM"
                    }
                
                analytics = runCommand("apic analytics-services:list --fields id,ingestion_endpoint,name,title,availability_zone_url,ingestion_endpoint_tls_client_profile_url --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
                analytics = yaml.safe_load(analytics)
                for eachAnalytics in analytics["results"]:
                    config["management_subsystem"][mgmtSubsystemName]["registered_analytics"][eachAnalytics["ingestion_endpoint"]] = {
                        "name": eachAnalytics["name"],
                        "title": eachAnalytics["title"],
                        "availability_zone_url": eachAnalytics["availability_zone_url"],
                        "id": eachAnalytics["id"],
                        "ingestion_endpoint_tls_client_profile_url": eachAnalytics["ingestion_endpoint_tls_client_profile_url"],
                    }

                    #add analytics info to mapping file
                    gateway_portal_mapping["analytics_mapping"][eachAnalytics["name"]] = {
                        eachAnalytics["ingestion_endpoint"]: "https://NEW_ANALYTICS_INGESTION_ENDPOINT_HOST_IN_TARGET_SYSTEM"
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
            mFile.write("#ai-endpoint url is the analytics ingestion url or https://NEW_ANALYTICS_INGESTION_ENDPOINT_HOST_IN_TARGET_SYSTEM on the right side\n")
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

    print ("CHECKING IF APICUP INSTALLER EXIST IN THE PATH :")
    output = runCommand("apicup version --accept-license")
    print()

    if os.path.exists("apiconnect-up.yml") == False: 
        print ("Time when error occurred :", time.asctime())
        print ("Copy this script to the v2018 project directory and run the script from that directory.")
        sys.exit("ERROR : Not running the script from v2018 project directory. apiconnect-up.yml NOT found. Exiting.")

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
            identityProviders = runCommand("apic identity-providers:list --scope admin --format yaml --server " + args.server, True)
            identityProviders = yaml.safe_load(identityProviders)["results"]
            matchFound = False
            validRealms = ""
            for each in identityProviders:
                realm = "admin/" + each["name"]
                validRealms = validRealms + "      For " + each["title"] + " " * (40 - len(each["title"])) + ", realm : " + realm + "\n"
                if args.realm == realm:
                    matchFound = True
            
            if matchFound == False:
                print ("Valid realms : ")
                print(validRealms)
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : Not a valid realm for the flag, Input realm value : [{}]. Exiting...".format(args.realm))
            runCommand("apic login --server " + args.server + " --realm " + args.realm + " --username " + args.username + " --password '" + args.password + "'", False, 1)
        cloudAdminServer = args.server
    print()
    
    if args.skip_mgmt == False:
        print ("Extract of management subsystem data will fail if 'apicops preupgrade' is not run within 2 hours of this script being run. ")
        confirm = input("Confirm that 'apicops preupgrade' command is run within 2 hours before running this script, type yes to confirm : ")
        if confirm != None: confirm = confirm.strip()
        confirm = confirm.lower()
        if (confirm != "yes"):
            print ("Time when error occurred :", time.asctime())
            sys.exit("ERROR : Run the 'apicops preupgrade' command and try running this script again. Exiting...")


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
	
parser = argparse.ArgumentParser(description="The script is used in form factor migration from v2018 to v10. It's run against a v2018 APIC cluster(source system) to collect configuration of management and\n\
portal subsystems so that the saved configuration can be used to migrate the data to the target form factor. The configuration is saved in data directory. \n\
If multiple gateway/portal subsystems are present in differnt namespaces, run the script again by pointing to the namespace.\n\n\
Prerequisites ::\n\
1. Access to the cluster (source system) using kubectl or oc.\n\
2. Python 3.x and PyYAML module need to be installed.\n\
3. Right version (v2018 fixpack being used) of apic toolkit must be in the path to run apic commands. Verify that the toolkit is able to connect to APIC system.\n\
4. Right version (v2018 fixpack being used) of apicup installer must be in the path to run apicup commands. Verify that the installer works.\n\
5. This script must be executed from inside the project directory of the v2018 project.\n\
6. The image needed to run extract job on the manageemnt subsystem must be loaded into the docker registry.\n\
7. apicops preupgrade command has to be executed before this script is run. The extract job will fail if the apicops preupgrade command is not run.\n\
8. Health check is performed on the subsystems.",
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

parser.add_argument("-export_cert", "--export_cert", action='store_true', dest = "export_cert", help="Exports ingress-ca and root-ca secrets.")

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

parser.add_argument("-storage_class", "--storage_class", dest = "storage_class", help="Storage class used by the upgrade PVC.")
parser.add_argument("-registry_secret", "--registry_secret", dest = "registry_secret", help="Registry secret of the registry where the v2018 extract docker image is present. This is optional and need to be given if required for the download of the image.")
parser.add_argument("-extract_image", "--extract_image", dest = "extract_image", help="The image value used to run extract pod which extracts v2018 management data. This is optional and used to override default value.")
parser.add_argument("-extract_storage_size", "--extract_storage_size", dest = "extract_storage_size", help="The storage request size used by the pvc in extract pod. Default is 10 GB. You need to give the value as a number 10 or 20 etc.")
parser.add_argument('-ocp', "--ocp", action='store_true', dest = "ocp", help='This flag must be provided in the input if the APIC environment is OCP/CP4I.')
parser.add_argument("-nginx_image", "--nginx_image", dest = "nginx_image", help="temporarily use this to download the csv files.")
parser.add_argument('-skip_csv_download', "--skip_csv_download", action='store_true', dest = "skip_csv_download", help='skips downloading extracted csv to local machine. The csv has to be explicitely downloaded externally by attaching to the pvc pvc-v2018-extract')

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


print ("Storage class used to create the pvc used by extract job (-storage_class or --storage_class flag) : ", args.storage_class)
print ("Extract image value. The extract image will be downloaded from this location (-extract_image or --extract_image flag) : ", args.extract_image)
print ("Registry secret used to download extract image from the registry. This is optional. (-registry_secret or --registry_secret flag) : ", args.registry_secret)
print ("Extract PVC storage size (-extract_storage_size or --extract_storage_size flag) : ", args.extract_storage_size)
print ("Is v2018 APIC on OCP/CP4I (-ocp or --ocp flag) : ", args.ocp)
print ("image using which csv is downloaded(-nginx_image or --nginx_image flag) : ", args.nginx_image)
print ("Skip csv download (-skip_csv_download or --skip_csv_download flag) : ", args.skip_csv_download)
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

if args.skip_mgmt == False and args.storage_class == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Storage class used by the upgrade pvc cannot be null. Use flag -storage_class or --storage_class to provide the storage class. Exiting...")

if args.skip_mgmt == False and args.extract_image == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Need to provide extract image used to extract data from v2018 management. Use flag -extract_image or --extract_image. Exiting...")


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