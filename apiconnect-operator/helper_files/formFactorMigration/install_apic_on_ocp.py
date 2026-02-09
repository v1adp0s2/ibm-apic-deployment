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

oc_client = "oc"
kubectl_client = "kubectl"
client = oc_client

pwd = None
DATA_DIR = None
DATA_TEMP_DIR = None

CONFIG_FILE_NAME = "config.yaml"
CONFIG_PORTAL_FILE_NAME = "config_portal.yaml"
config =  None
config_portal =  None
mgmtSubsystemDetails = None
portalSubsystemDetails = None

ocpVersion = None
certManagerType = None

mgmtCustomApplicationSecrets = ["atm-cred", "ccli-cred", "cui-cred", "dsgr-cred", "juhu-cred", "cli-cred", "ui-cred"]
ADDITIONAL_PROFILES_IF_REMOTE_GATEWAY = ["n1xc12.m64", "n3xc12.m56"]

# LTS RELEASE (for now 10.0.8.x)
LTS_CP4I_VERSION = "16.1.0" # check for correct values before GA
LTS_PN_CHANNEL = "v7.3-sc2" # check for correct values before GA
LTS_APIC_CHANNEL = "v5.8-sc2"  # check for correct values before GA
LTS_DP_CHANNEL = "v1.11-sc2"  # check for correct values before GA
LTS_APIC_VERSION = "10.0.8.6" # check for correct values before GA
LTS_APIC_PROFILES = ["n1xc7.m48", "n1xc16.m72", "n3xc16.m64"]

#CD RELEASE
CD_CP4I_VERSION = "16.1.0" # check for correct values before GA
CD_PN_CHANNEL = "v7.3-sc2" # check for correct values before GA
CD_APIC_CHANNEL = "v5.2-sc2" # check for correct values before GA
CD_DP_CHANNEL = "v1.11-sc2"  # check for correct values before GA
CD_APIC_VERSION = "10.0.8.0" # check for correct values before GA
CD_APIC_PROFILES = ["n1xc7.m48", "n1xc16.m72", "n3xc16.m64"]

# keep changing this value based on the branch LTS OR CD branch 
ltsRelease = True
LTS_OCP_VERSIONS = ["4.12", "4.14", "4.15", "4.16", "4.17", "4.18", "4.19", "4.20"] # check for correct values before GA

DEFAULT_COMMON_SERVICES_CHANNEL = "v4.6" # check for correct values before GA
DEFAULT_IBM_CERT_MANAGER_CHANNEL = "v4.2" # check for correct values before GA
DEFAULT_REDHAT_CERT_MANAGER_CHANNEL = "stable-v1" # check for correct values before GA

DEFAULT_CERT_MANAGER_TYPE = "redhat"
CERT_MANAGER_TYPES = ["ibm", "redhat", "other"]

cp4iVersion = CD_CP4I_VERSION
apicChannel = CD_APIC_CHANNEL
dpChannel = CD_DP_CHANNEL
apicVersion = CD_APIC_VERSION
platformNavigatorChannel = CD_PN_CHANNEL
profiles = CD_APIC_PROFILES

if ltsRelease:
    cp4iVersion = LTS_CP4I_VERSION
    apicChannel = LTS_APIC_CHANNEL
    dpChannel = LTS_DP_CHANNEL
    apicVersion = LTS_APIC_VERSION
    platformNavigatorChannel = LTS_PN_CHANNEL
    profiles = LTS_APIC_PROFILES


#ibm cert manager catalog source
ibm_cert_manager_catsrc = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "CatalogSource",
  "metadata": {
    "name": "ibm-cert-manager-catalog",
    "namespace": "openshift-marketplace"
  },
  "spec": {
    "displayName": "ibm-cert-manager",
    "publisher": "IBM",
    "sourceType": "grpc",
    "image": "icr.io/cpopen/ibm-cert-manager-operator-catalog",
    "updateStrategy": {
      "registryPoll": {
        "interval": "45m"
      }
    }
  }
}

ns_obj = {
  "apiVersion": "v1",
  "kind": "Namespace",
  "metadata": {
    "name": "TBD"
  }
}

#ibm cert manager subscription
ibm_cert_manager_subscribe = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "Subscription",
  "metadata": {
    "labels": {
      "operators.coreos.com/ibm-cert-manager-operator.ibm-cert-manager": ""
    },
    "name": "ibm-cert-manager-operator",
    "namespace": "ibm-cert-manager"
  },
  "spec": {
    "channel": "TBD",
    "installPlanApproval": "Automatic",
    "name": "ibm-cert-manager-operator",
    "source": "ibm-operator-catalog",
    "sourceNamespace": "openshift-marketplace"
  }
}

#redhat cert manager subscription
redhat_cert_manager_subscribe = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "Subscription",
  "metadata": {
    "labels": {
      "operators.coreos.com/openshift-cert-manager-operator.cert-manager-operator": ""
    },
    "name": "openshift-cert-manager-operator",
    "namespace": "cert-manager-operator"
  },
  "spec": {
    "channel": "TBD",
    "installPlanApproval": "Automatic",
    "name": "openshift-cert-manager-operator",
    "source": "redhat-operators",
    "sourceNamespace": "openshift-marketplace"
  }
}

#common services for lts
opencloud_operators_catsrc = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "CatalogSource",
  "metadata": {
    "name": "opencloud-operators",
    "namespace": "openshift-marketplace"
  },
  "spec": {
    "displayName": "IBMCS Operators",
    "image": "docker-na-public.artifactory.swg-devops.com/hyc-cloud-private-daily-docker-local/ibmcom/ibm-common-service-catalog:latest",
    "publisher": "IBM",
    "sourceType": "grpc",
    "updateStrategy": {
      "registryPoll": {
        "interval": "45m"
      }
    }
  }
}

#used for cp4i as per kc docs, both same
ibmOperatorCatalog1 = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "CatalogSource",
  "metadata": {
    "name": "ibm-operator-catalog",
    "namespace": "openshift-marketplace"
  },
  "spec": {
    "displayName": "IBM Operator Catalog",
    "image": "icr.io/cpopen/ibm-operator-catalog:latest",
    "publisher": "IBM",
    "sourceType": "grpc",
    "updateStrategy": {
      "registryPoll": {
        "interval": "45m"
      }
    }
  }
}

redhat_keycloak_catsrc = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "CatalogSource",
  "metadata": {
    "name": "keycloak-rhbk-catalog-ibm",
    "namespace": "openshift-marketplace"
  },
  "spec": {
    "displayName": "keycloak-rhbk-catalog-ibm",
    "publisher": "RH Keycloak by IBM Dev",
    "sourceType": "grpc",
    "image": "cp.stg.icr.io/cp/abp-keycloak/keycloak-rhbk-catalog-ibm:latest",
    "updateStrategy": {
      "registryPoll": {
        "interval": "45m"
      }
    }
  }
}

redhat_build_keycloak_icsp = {
  "apiVersion": "operator.openshift.io/v1alpha1",
  "kind": "ImageContentSourcePolicy",
  "metadata": {
    "name": "ibm-rhbk-driver-icsp"
  },
  "spec": {
    "repositoryDigestMirrors": [
      {
        "mirrors": [
          "cp.stg.icr.io/cp/abp-keycloak"
        ],
        "source": "registry.redhat.io/rhbk"
      }
    ]
  }
}

operator_group_v1 = {
  "apiVersion": "operators.coreos.com/v1",
  "kind": "OperatorGroup",
  "metadata": {
    "name": "tbd-operator-group",
    "namespace": "TBD"
  },
  "spec": {
    "targetNamespaces": [],
    "upgradeStrategy": "Default"
  }
}

operator_group_v1alpha2 = {
  "apiVersion": "operators.coreos.com/v1alpha2",
  "kind": "OperatorGroup",
  "metadata": {
    "name": "tbd-operator-group",
    "namespace": "TBD"
  },
  "spec": {}
}

common_services_subscribe = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "Subscription",
  "metadata": {
    "name": "ibm-common-service-operator",
    "namespace": "test1"
  },
  "spec": {
    "channel": "TBD",
    "installPlanApproval": "Automatic",
    "name": "ibm-common-service-operator",
    "source": "ibm-operator-catalog",
    "sourceNamespace": "openshift-marketplace"
  }
}

apiconnect_subscribe = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "Subscription",
  "metadata": {
    "name": "ibm-apiconnect",
    "namespace": "TBD"
  },
  "spec": {
    "channel": apicChannel,
    "installPlanApproval": "Automatic",
    "name": "ibm-apiconnect",
    "source": "ibm-operator-catalog",
    "sourceNamespace": "openshift-marketplace"
  }
}

datapower_subscribe = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "Subscription",
  "metadata": {
    "name": "datapower-operator",
    "namespace": "TBD"
  },
  "spec": {
    "channel": dpChannel,
    "installPlanApproval": "Automatic",
    "name": "datapower-operator",
    "source": "ibm-operator-catalog",
    "sourceNamespace": "openshift-marketplace",
  }
}

#platform navigator catalog source
pn_catalog_source_dailybuild = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "CatalogSource",
  "metadata": {
    "name": "ibm-platform-navigator-catalog",
    "namespace": "openshift-marketplace"
  },
  "spec": {
    "displayName": "ibm-platform-navigator-catalog",
    "publisher": "IBM Content",
    "sourceType": "grpc",
    "image": "cp.stg.icr.io/cp/ibm-integration-platform-navigator-catalog:latest-cd",
    "updateStrategy": {
      "registryPoll": {
        "interval": "45m"
      }
    }
  }
}


pn_subscribe = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "Subscription",
  "metadata": {
    "name": "ibm-integration-platform-navigator",
    "namespace": "TBD"
  },
  "spec": {
    "channel": platformNavigatorChannel,
    "installPlanApproval": "Automatic",
    "name": "ibm-integration-platform-navigator",
    "source": "ibm-operator-catalog",
    "sourceNamespace": "openshift-marketplace"
  }
}


topLevelCR = {
  "apiVersion": "apiconnect.ibm.com/v1beta1",
  "kind": "APIConnectCluster",
  "metadata": {
    "name": "minimum",
    "labels": {
      "app.kubernetes.io/instance": "apiconnect",
      "app.kubernetes.io/managed-by": "ibm-apiconnect",
      "app.kubernetes.io/name": "apiconnect-minimum"
    },
    "namespace": "TBD"
  },
  "spec": {
    "license": {
      "accept": True,
      "use": "nonproduction"
    },
    "storageClassName": "TBD",
    "profile": "TBD",
    "version": "TBD",
    "management": {
      "name": "TBD",
      "originalUID": "TBD",
      "customApplicationCredentials": [],
      "siteName": "TBD",
      "encryptionSecret": {},
      "databaseBackup": {}
    },
    "analytics": {
      "mtlsValidateClient": True,
      "ingestion": {
        "queue": {
          "type": "persisted"
        }
      },
      "storage": {
        "enabled": True
      }
    },
    "portal": {
      "mtlsValidateClient": True,
      "name": "tbd",
      "originalUID": "TBD",
      "encryptionSecret": {},
      "portalBackup": {},
      "siteName": "TBD"
    }
  }
}

#ibm edb postgres catalog source
edb_postgres_catalog_source = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "CatalogSource",
  "metadata": {
    "name": "ibm-edb-postgres-catalog",
    "namespace": "openshift-marketplace"
  },
  "spec": {
    "displayName": "IBM EDB Postgres Operator",
    "image": "icr.io/cpopen/ibm-cpd-cloud-native-postgresql-operator-catalog@sha256:f12d3a6607555c61fa7a50c4b82e67b54e477ff958e34fb0b5b2e9361f1a4d96",
    "publisher": "IBM",
    "sourceType": "grpc",
    "updateStrategy": {
      "registryPoll": {
        "interval": "45m"
      }
    }
  }
}

apiconnect_catalog_source = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "CatalogSource",
  "metadata": {
    "name": "ibm-apiconnect-catalog",
    "namespace": "openshift-marketplace"
  },
  "spec": {
    "displayName": "IBM APIConnect catalog",
    "image": "icr.io/cpopen/ibm-apiconnect-catalog:latest",
    "publisher": "IBM",
    "sourceType": "grpc",
    "grpcPodConfig": {
        "securityContextConfig": "restricted"
    },
    "updateStrategy": {
      "registryPoll": {
        "interval": "45m"
      }
    }
  }
}

datapower_catalog_source = {
  "apiVersion": "operators.coreos.com/v1alpha1",
  "kind": "CatalogSource",
  "metadata": {
    "name": "ibm-datapower-operator-catalog",
    "namespace": "openshift-marketplace"
  },
  "spec": {
    "displayName": "DataPower Operator",
    "publisher": "IBM Content",
    "sourceType": "grpc",
    "grpcPodConfig": {
        "securityContextConfig": "restricted"
    },
    "image": "icr.io/cpopen/datapower-operator-catalog:latest",
    "updateStrategy": {
      "registryPoll": {
        "interval": "45m"
      }
    }
  }
}


pn_instance_yaml = {
  "apiVersion": "integration.ibm.com/v1beta1",
  "kind": "PlatformNavigator",
  "metadata": {
    "name": "integration-navigator",
    "namespace": "TBD"
  },
  "spec": {
    "license": {
      "accept": True,
      "license": "TBD"
    },
    "version": cp4iVersion,
    "replicas": 1
  }
}

ERRORED_TIME_MESSAGE = "Time when error occurred :"

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
                    print (ERRORED_TIME_MESSAGE, time.asctime())
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
                    sys.exit("ERROR : Health check failed for {} subsystem with name {}. Phase : {} and state : {}".format(subsystem, subsystemName, crData["status"]["phase"], crData["status"]["state"]))
                print ("ACTION OUTPUT : {} with name {} is healthy".format(subsystem, subsystemName))
            print ()
    else:
        print ("ACTION OUTPUT : Skipping health check for {} subsytem as namespace is NOT provided in the input. Given namespace is {}".format(subsystem, ns))


def waitForResourceCreation(command1, namespace1, resourceName, resourceType):
    flag = True
    loopCount = 0
    timeout = False
    while flag:
        loopCount = loopCount + 1
        if loopCount >= 30:
            flag = False
            print ("Timeout after Waiting for creation of resource, " + resourceName + " of type " + resourceType)
            timeout = True
            break # safe break after 10 min
        response1 = runKubernetesCommand(command1, namespace1, True, 0, False)
        if response1 != None and response1 != "" and response1.lower().startswith("error") == False:
            response1 = response1.splitlines()
            for r1 in response1:
                if r1.startswith(resourceName):
                    flag = False
                    break

        if flag == True:
            print ("Waiting for creation of resource, " + resourceName + " of type " + resourceType)
            time.sleep(30)
        else:
            break
    
    if timeout == True:
        sys.exit("Try again. Timed out waiting for creation of resource, " + resourceName + " of type " + resourceType)


def subscribe_common_services(namespace):
    print("Subscribe to common services")
    common_services_ns = namespace

    if common_services_ns == "openshift-operators":
        create_namespace("ibm-common-services")

    subscriptions = runKubernetesCommand("get subscription", common_services_ns, False)
    subscriptions = subscriptions.splitlines()
    subscriptionsList = []
    for eachSub in subscriptions:
        subscriptionsList.append(eachSub[0:eachSub.index(" ")])
    if "ibm-common-service-operator" in subscriptionsList:
        print("ACTION OUTPUT : common services already subscribed in the namespace, ", common_services_ns)
        print()
    else:
        common_services_subscribe["spec"]["channel"] = DEFAULT_COMMON_SERVICES_CHANNEL
        label_key = "operators.coreos.com/ibm-common-service-operator." + common_services_ns
        common_services_subscribe["metadata"]["labels"] = {
            label_key : ""
        }
        common_services_subscribe["metadata"]["namespace"] = common_services_ns
        if args.common_services_channel != None:
            common_services_subscribe["spec"]["channel"] = args.common_services_channel
        else:
            if ltsRelease and args.cp4i: # For LTS, PN will be tied to a specific CS channel
                common_services_subscribe["spec"]["channel"] = DEFAULT_COMMON_SERVICES_CHANNEL
        print("ACTION OUTPUT : Using common services channel version : ", common_services_subscribe["spec"]["channel"])

        if args.custom_build:
            common_services_subscribe["spec"]["source"] = "opencloud-operators"

        common_services_sub_fileName = DATA_TEMP_DIR + "/subscription_common_services.yaml"
        with open(common_services_sub_fileName, 'w') as commonServicesSubFile:
            yaml.dump(common_services_subscribe, commonServicesSubFile, default_flow_style=False)
        if args.no_install == False:
            runKubernetesCommand("create -f " + common_services_sub_fileName, common_services_ns, False)
            waitForResourceCreation("get subscription", common_services_ns, "ibm-common-service-operator", "subscription")
            print("ACTION OUTPUT : Subscribed to common services in namespace, ", common_services_ns)
            time.sleep(90)
        else:
            print("no_install flag is set to true. Not subscribing to common services.")
            print("ACTION OUTPUT : Location of common-services subscription yaml file : ", common_services_sub_fileName)
            print()

def subscribe_cert_manager():
    print("Subscribe to cert manager")
    cert_manager_op_namespace = None
    cert_manager_subscription_name = None
    subscription_object = None

    if certManagerType == "ibm":
        cert_manager_op_namespace = "ibm-cert-manager"
        if args.cert_manager_operator_namespace != None:
            cert_manager_op_namespace = args.cert_manager_operator_namespace
        
        operator_group_v1["spec"]["targetNamespaces"] = []
        cert_manager_subscription_name = "ibm-cert-manager-operator"
        if args.custom_build == True:
            ibm_cert_manager_subscribe["spec"]["source"] = "ibm-cert-manager-catalog"
        ibm_cert_manager_subscribe["spec"]["channel"] = DEFAULT_IBM_CERT_MANAGER_CHANNEL
        subscription_object = ibm_cert_manager_subscribe
        create_namespace(cert_manager_op_namespace)
        create_operator_group_v1alpha2("cert-manager-operator-group", cert_manager_op_namespace, None)

    elif certManagerType == "redhat":
        cert_manager_op_namespace = "cert-manager-operator"
        if args.cert_manager_operator_namespace != None:
            cert_manager_op_namespace = args.cert_manager_operator_namespace

        operator_group_v1["spec"]["targetNamespaces"] = [cert_manager_op_namespace]
        cert_manager_subscription_name = "openshift-cert-manager-operator"
        redhat_cert_manager_subscribe["spec"]["channel"] = DEFAULT_REDHAT_CERT_MANAGER_CHANNEL
        subscription_object = redhat_cert_manager_subscribe
        create_namespace(cert_manager_op_namespace)
        create_operator_group_v1alpha2("cert-manager-operator-group", cert_manager_op_namespace, [cert_manager_op_namespace])
    
    if certManagerType != "other":
        subscription_object["metadata"]["namespace"] = cert_manager_op_namespace
        create_operator_group("cert-manager-operator-group-v1", cert_manager_op_namespace) 

        subscriptions = runKubernetesCommand("get subscription", cert_manager_op_namespace, False)
        subscriptions = subscriptions.splitlines()
        subscriptions_list = []
        for each_sub in subscriptions:
            subscriptions_list.append(each_sub[0:each_sub.index(" ")])

        if cert_manager_subscription_name in subscriptions_list:
            print("ACTION OUTPUT : Cert manager with name, {} already subscribed in the namespace, {}".format(cert_manager_subscription_name, cert_manager_op_namespace))
            print()
        else:
            if args.cert_manager_channel != None:
                subscription_object["spec"]["channel"] = args.cert_manager_channel
            
            print("ACTION OUTPUT : Using cert manager, {} and  channel version, {} ".format(cert_manager_subscription_name, subscription_object["spec"]["channel"]))

            cert_manager_sub_filename = DATA_TEMP_DIR + "/subscription_cert_manager.yaml"
            with open(cert_manager_sub_filename, 'w') as certManagerSubFile:
                yaml.dump(subscription_object, certManagerSubFile, default_flow_style=False)

            if args.no_install == False:
                runKubernetesCommand("create -f " + cert_manager_sub_filename, cert_manager_op_namespace, False)
                waitForResourceCreation("get subscription", cert_manager_op_namespace, cert_manager_subscription_name, "subscription")
                print("ACTION OUTPUT : Subscribed to {} cert manager in namespace, {}".format(certManagerType, cert_manager_op_namespace))
                time.sleep(90)
            else:
                print("no_install flag is set to true. Not subscribing to crt manager.")
                print("ACTION OUTPUT : Location of cert manager subscription yaml file : ", cert_manager_sub_filename)
                print()
    else:
        print("ACTION OUTPUT : Other cert manager selected. The cert manager must be subscribed already before running this script.")

 # namespace create
def create_namespace(name):
    ns_names = runKubernetesCommand("get namespace", name, True)
    ns_names = ns_names.splitlines()
    if (name not in ns_names):
        ns_obj["metadata"]["name"] = name
        ns_filename = DATA_TEMP_DIR + "/ns_" + name + ".yaml"
        with open(ns_filename, 'w') as file2:
            yaml.dump(ns_obj, file2, default_flow_style=False)
        if args.no_install == False:
            runKubernetesCommand("apply -f " + ns_filename, args.ns, False)
            print("ACTION OUTPUT : Created the namespace")
        else:
            print("no_install flag is set to true. Not creating namespace with name, {}".format(name))
            print("ACTION OUTPUT : Location of create namespace yaml file : ", ns_filename)
    else:
        print("ACTION OUTPUT : Looks like namespace is already created.")
    print()


 # operator group
def create_operator_group(og_name, namespace):
    ogs = runKubernetesCommand("get operatorgroup", namespace, False)
    ogs = ogs.splitlines()
    if (len(ogs) <= 1):
        operator_group_v1["metadata"]["namespace"] = namespace
        operator_group_v1["metadata"]["name"] = og_name
        operator_group_filename = DATA_TEMP_DIR + "/og_" + og_name + ".yaml"
        with open(operator_group_filename, 'w') as file2:
            yaml.dump(operator_group_v1, file2, default_flow_style=False)
        if args.no_install == False:
            runKubernetesCommand("apply -f " + operator_group_filename, namespace, False)
            print("ACTION OUTPUT : Created/applied operator group for the namespace")
        else:
            print("no_install flag is set to true. Not installing operator group with name, {} in namespace, {}".format(og_name, namespace))
            print("ACTION OUTPUT : Location of operator group file : ", operator_group_filename)
    else:
        print("ACTION OUTPUT : Looks like operator group is already installed.")
    print()

 # operator group v1alpha2
def create_operator_group_v1alpha2(og_name, namespace, target_namespaces):
    ogs = runKubernetesCommand("get operatorgroup", namespace, False)
    ogs = ogs.splitlines()
    if (len(ogs) <= 1):
        operator_group_v1alpha2["metadata"]["namespace"] = namespace
        operator_group_v1alpha2["metadata"]["name"] = og_name
        if target_namespaces != None:
            operator_group_v1alpha2["spec"]["targetNamespaces"] = target_namespaces
        else:
            operator_group_v1alpha2["spec"] = {} 
        operator_group_filename = DATA_TEMP_DIR + "/og_v1alpha2_" + og_name + ".yaml"
        with open(operator_group_filename, 'w') as file2:
            yaml.dump(operator_group_v1alpha2, file2, default_flow_style=False)
        if args.no_install == False:
            runKubernetesCommand("apply -f " + operator_group_filename, namespace, False)
            print("ACTION OUTPUT : Created/applied operator group for the namespace")
        else:
            print("no_install flag is set to true. Not installing operator group with name, {} in namespace, {}".format(og_name, namespace))
            print("ACTION OUTPUT : Location of operator group file : ", operator_group_filename)
    else:
        print("ACTION OUTPUT : Looks like operator group is already installed.")
    print()


def install_catalog_sources_and_subscribe():
    global certManagerType
    print ("Check and install catalog sources::")

    #catalog sources list
    catalogsources = runKubernetesCommand("get catalogsource", "openshift-marketplace", False)
    catalogsources = catalogsources.splitlines()
    catalogsourcesList = []
    for eachCatSrc in catalogsources:
        catalogsourcesList.append(eachCatSrc[0:eachCatSrc.index(" ")])

    # cert manager type
    if args.cert_manager_type is None:
        certManagerType = DEFAULT_CERT_MANAGER_TYPE
    else:
        certManagerType = args.cert_manager_type.strip()
        if certManagerType not in CERT_MANAGER_TYPES:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("Invalid cert manager type provided for flag cert_manager_type. valid values are " + CERT_MANAGER_TYPES)

    if certManagerType == "redhat":
        print ("ACTION OUTPUT : Red Hat operators catalog source(for cert manager etc) present by default in OCP.")
    elif certManagerType == "other":
        confirm =  input("Already installed the cert manager supported by IBM API Connect manually, confirm yes or no : ")
        if confirm != "yes":
            sys.exit("Install the cert manager manually and try again.")

    if args.custom_build == False:
        #ibm operator catalog
        if "ibm-operator-catalog" in catalogsourcesList:
            print("ACTION OUTPUT : ibm-operator-catalog catalog source already installed.")
        else:
            ibmOperatorCatSrcFileName = DATA_TEMP_DIR + "/catsrc_ibm_operator_catalog.yaml"
            with open(ibmOperatorCatSrcFileName, 'w') as file1:
                yaml.dump(ibmOperatorCatalog1, file1, default_flow_style=False)
            if args.no_install == False:
                runKubernetesCommand("create -f " +ibmOperatorCatSrcFileName, "openshift-marketplace", False)
                waitForResourceCreation("get catalogsource", "openshift-marketplace", "ibm-operator-catalog", "catalog source")
                print("ACTION OUTPUT : Created ibm-operator-catalog catalog source")
            else:
                print("no_install flag is set to true. Not installing ibm-operator-catalog catalog source.")
                print("ACTION OUTPUT : Location of ibm-operator-catalog catalog source file : ", ibmOperatorCatSrcFileName)
                print()
        
        if args.no_install == False:
            runKubernetesCommand("get packagemanifests | grep ibm-common-service", "openshift-marketplace", False) 
            runKubernetesCommand("get packagemanifests | grep apiconnect", "openshift-marketplace", False)
            runKubernetesCommand("get packagemanifests | grep datapower", "openshift-marketplace", False)

        if certManagerType == "ibm":
            print ("ACTION OUTPUT : IBM cert manager catalog available as part of IBM operator catalog source.")

    else:
        #custom build
        ##############

        # install ibm-cert-manager-catalog
        if certManagerType == "ibm":
            if "ibm-cert-manager-catalog" in catalogsourcesList:
                print("ACTION OUTPUT : ibm-cert-manager-catalog catalog source already installed.")
            else:
                ibm_cert_manager_catsrc_filename = DATA_TEMP_DIR + "/catsrc_ibm_cert_manager_catalog.yaml"
                with open(ibm_cert_manager_catsrc_filename, 'w') as file1:
                    yaml.dump(ibm_cert_manager_catsrc, file1, default_flow_style=False)
                if args.no_install == False:
                    runKubernetesCommand("create -f " +ibm_cert_manager_catsrc_filename, "openshift-marketplace", False)
                    waitForResourceCreation("get catalogsource", "openshift-marketplace", "ibm-cert-manager-catalog", "catalog source")
                    print("ACTION OUTPUT : Created ibm-cert-manager-catalog catalog source")
                    time.sleep(60)
                else:
                    print("no_install flag is set to true. Not installing ibm-cert-manager-catalog catalog source.")
                    print("ACTION OUTPUT : Location of ibm-cert-manager-catalog catalog source file : ", ibm_cert_manager_catsrc_filename)
                    print()

        #common services catalog source
        if "opencloud-operators" in catalogsourcesList:
            print("ACTION OUTPUT : common services catalog source already installed.")
            print()
        else:
            common_services_fileName = DATA_TEMP_DIR + "/catsrc_common_services.yaml"
            with open(common_services_fileName, 'w') as commonServicesFile:
                yaml.dump(opencloud_operators_catsrc, commonServicesFile, default_flow_style=False)
            if args.no_install == False:
                runKubernetesCommand("create -f " + common_services_fileName, "openshift-marketplace", False)
                waitForResourceCreation("get catalogsource", "openshift-marketplace", "opencloud-operators", "catalog source")
                print("ACTION OUTPUT : Created common services catalog source")
                time.sleep(60)
            else:
                print("no_install flag is set to true. Not installing common-services catalog source.")
                print("ACTION OUTPUT : Location of common-services catalog source file : ", common_services_fileName)
                print()
        if args.no_install == False:
            runKubernetesCommand("get packagemanifests | grep common-service", "openshift-marketplace", False, 10)
        print()

        #apiconnect catalog source
        if args.apic_catsrc_image == None or args.apic_catsrc_image == "":
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("Custom build apiconnect catalog source image value not provided. Exiting. Use the flag -apic_catsrc_image to provide it")

        if "ibm-apiconnect-catalog" in catalogsourcesList:
            print("ibm-apiconnect-catalog catalog source already installed. Checking if the image matches..")
            res1 = runKubernetesCommand("get catalogsource ibm-apiconnect-catalog -o yaml", "openshift-marketplace", True)
            res1 = yaml.safe_load(res1)
            if res1["spec"]["image"] == args.apic_catsrc_image:
                print("ACTION OUTPUT : Installed ibm-apiconnect-catalog catalog source image value matches the input image value. Proceeding further")
            else:
                print (ERRORED_TIME_MESSAGE, time.asctime())
                sys.exit("Installed ibm-apiconnect-catalog catalog source image value({}) does NOT match the input image value({}). Delete the ibm-apiconnect-catalog catalog source and try again.".format(res1["spec"]["image"] , args.apic_catsrc_image))
        else:
            apiconnect_catalog_source["spec"]["image"] = args.apic_catsrc_image
            apiConnectCatSrcFileName = DATA_TEMP_DIR + "/catsrc_apic_connect_catalog.yaml"
            with open(apiConnectCatSrcFileName, 'w') as file2:
                yaml.dump(apiconnect_catalog_source, file2, default_flow_style=False)
            if args.no_install == False:
                runKubernetesCommand("create -f " + apiConnectCatSrcFileName, "openshift-marketplace", False)
                waitForResourceCreation("get catalogsource", "openshift-marketplace", "ibm-apiconnect-catalog", "catalog source")
                print("ACTION OUTPUT : Created ibm-apiconnect-catalog catalog source using custom image : ", args.apic_catsrc_image)
            else:
                print("no_install flag is set to true. Not installing ibm-apiconnect-catalog catalog source.")
                print("ACTION OUTPUT : Location of ibm-apiconnect-catalog catalog source file : ", apiConnectCatSrcFileName)
        print()
        
        #datapower catalog source
        if args.dp_catsrc_image == None or args.dp_catsrc_image == "":
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("Custom build datapower catalog source image value not provided. Exiting. Use the flag -dp_catsrc_image to provide it")

        if "ibm-datapower-operator-catalog" in catalogsourcesList:
            print("ibm-datapower-operator-catalog catalog source already installed. Checking if the image matches..")
            res1 = runKubernetesCommand("get catalogsource ibm-datapower-operator-catalog -o yaml", "openshift-marketplace", True)
            res1 = yaml.safe_load(res1)
            if res1["spec"]["image"] == args.dp_catsrc_image:
                print("ACTION OUTPUT : Installed ibm-datapower-operator-catalog catalog source image value matches the input image value. Proceeding further")
            else:
                print (ERRORED_TIME_MESSAGE, time.asctime())
                sys.exit("Installed ibm-datapower-operator-catalog catalog source image value({}) does NOT match the input image value({}). Delete the ibm-datapower-operator-catalog catalog source and try again".format(res1["spec"]["image"] , args.apic_catsrc_image))
        else:
            datapower_catalog_source["spec"]["image"] = args.dp_catsrc_image
            dpConnectCatSrcFileName = DATA_TEMP_DIR + "/catsrc_datapower_catalog.yaml"
            with open(dpConnectCatSrcFileName, 'w') as file2:
                yaml.dump(datapower_catalog_source, file2, default_flow_style=False)
            if args.no_install == False:
                runKubernetesCommand("create -f " + dpConnectCatSrcFileName, "openshift-marketplace", False)
                waitForResourceCreation("get catalogsource", "openshift-marketplace", "ibm-datapower-operator-catalog", "catalog source")
                print("ACTION OUTPUT : Created ibm-datapower-operator-catalog catalog source using custom image : ", args.dp_catsrc_image)
            else:
                print("no_install flag is set to true. Not installing ibm-datapower-operator-catalog catalog source.")
                print("ACTION OUTPUT : Location of ibm-datapower-operator-catalog catalog source file : ", dpConnectCatSrcFileName)
        print()
    
    if args.cp4i and args.custom_build:
        """
        if "keycloak-rhbk-catalog-ibm" in catalogsourcesList:
            print("ACTION OUTPUT : Red Hat Key cloak(keycloak-rhbk-catalog-ibm) catalog source already installed.")
            print()
        else:
            rh_keycloak_catsrc_filename = DATA_TEMP_DIR + "/redhat_keycloak_catsrc.yaml"
            with open(rh_keycloak_catsrc_filename, 'w') as rhKeyCloakFile:
                yaml.dump(redhat_keycloak_catsrc, rhKeyCloakFile, default_flow_style=False)
            if args.no_install == False:
                runKubernetesCommand("create -f " + rh_keycloak_catsrc_filename, "openshift-marketplace", False)
                waitForResourceCreation("get catalogsource", "openshift-marketplace", "keycloak-rhbk-catalog-ibm", "catalog source")
                print("ACTION OUTPUT : Created Red Hat Key cloak(keycloak-rhbk-catalog-ibm) catalog source")
                time.sleep(60)
            else:
                print("no_install flag is set to true. Not installing Red Hat Key cloak(keycloak-rhbk-catalog-ibm) catalog source.")
                print("ACTION OUTPUT : Location of Red Hat Key cloak(keycloak-rhbk-catalog-ibm) catalog source file : ", rh_keycloak_catsrc_filename)
                print()
        if args.no_install == False:
            runKubernetesCommand("get packagemanifests | grep keycloak-rhbk-catalog-ibm", "openshift-marketplace", False, 10)
        print()

        # temporary icsp for redhat build of keycloak (rhbk)
        icsp_rhbk_filename = DATA_TEMP_DIR + "/icsp_for_redhat_keycloak.yaml"
        with open(icsp_rhbk_filename, 'w') as rhbk_icsp_file:
            yaml.dump(redhat_build_keycloak_icsp, rhbk_icsp_file, default_flow_style=False)
    
        if args.no_install == False:
            print("Location of icsp to use redhat build of keycloak : ", icsp_rhbk_filename)
            runKubernetesCommand("apply -f " + icsp_rhbk_filename, "openshift-marketplace", False, 50)
            time.sleep(30)
        """

        # PN catalog source
        if "ibm-platform-navigator-catalog" in catalogsourcesList:
            print("ACTION OUTPUT : ibm-platform-navigator-catalog catalog source already installed. Proceeding further.")
        else:
            if args.pn_catsrc_image != None and args.pn_catsrc_image != "":
                pn_catalog_source_dailybuild["spec"]["image"] = args.pn_catsrc_image

            pnCatSrcFileName = DATA_TEMP_DIR + "/catsrc_platform_nav.yaml"
            with open(pnCatSrcFileName, 'w') as file1:
                yaml.dump(pn_catalog_source_dailybuild, file1, default_flow_style=False)
            if args.no_install == False:
                runKubernetesCommand("create -f " +pnCatSrcFileName, "openshift-marketplace", False)
                waitForResourceCreation("get catalogsource", "openshift-marketplace", "ibm-platform-navigator-catalog", "catalog source")
                print("ACTION OUTPUT : Created ibm-platform-navigator-catalog catalog source needed for Platform Navigator.")
            else:
                print("no_install flag is set to true. Not installing ibm-platform-navigator-catalog catalog source.")
                print("ACTION OUTPUT : Location of ibm-platform-navigator-catalog catalog source file : ", pnCatSrcFileName)
                print()
    
    time.sleep(120)

    # subscribe cert manager
    subscribe_cert_manager()
    
    operator_group_v1["spec"]["targetNamespaces"] = [args.ns]
    create_operator_group("apic-operator-group", args.ns)

    # apic/dp/common service/PN operator namespace
    namespace = None
    if args.operator_in_specific_namespace:
        namespace = args.ns
    else:
        namespace = "openshift-operators"
    
    # subscribe common services
    subscribe_common_services(namespace)

    #platform navigator subscription
    if args.cp4i:
        #check if platform navigator subscription exists
        #namespace will be same as what apic is subscribed to.
        subscriptions = runKubernetesCommand("get subscription", namespace, False)
        subscriptions = subscriptions.splitlines()
        subscriptionExists = False
        for eachSubscription in subscriptions:
            if "ibm-integration-platform-navigator" in eachSubscription:
                pnSubscriptionName = eachSubscription[0:eachSubscription.index(" ")]
                pnSubscription = runKubernetesCommand("get subscription " + pnSubscriptionName + " -o yaml", namespace, True)
                pnSubscription = yaml.safe_load(pnSubscription)
                channel = pnSubscription["spec"]["channel"]
                if channel == platformNavigatorChannel:
                    subscriptionExists = True
                    print("ACTION OUTPUT : Platform navigator already subscribed for channel number, " + platformNavigatorChannel + " Not installing again. Proceeding further.")
                    print()
                else:
                    print (ERRORED_TIME_MESSAGE, time.asctime())
                    sys.exit("Platform navigator already subscribed for different channel number, " + channel + " Uninstall it and try again. This script uses PN channel " + platformNavigatorChannel)

        if subscriptionExists == False:
            if args.custom_build:
                pn_subscribe["spec"]["source"] = "ibm-platform-navigator-catalog"

            pn_subscribe["metadata"]["namespace"] = namespace
            subscribe_pn_FileName = DATA_TEMP_DIR + "/subscription_pn.yaml"
            with open(subscribe_pn_FileName, 'w') as file2:
                yaml.dump(pn_subscribe, file2, default_flow_style=False)
            if args.no_install == False:
                runKubernetesCommand("create -f " + subscribe_pn_FileName, namespace, False)
                time.sleep(120)
                print("ACTION OUTPUT : Created subscription for platform navigator.")
            else:
                print("no_install flag is set to true. Not installing platform navigator.")
                print("ACTION OUTPUT : Location of platform navigator subscription file : ", subscribe_pn_FileName)
                print()
        
        # check if PN subscription is created
        if args.no_install == False:
            flag = True
            loopCount = 0
            timeout = False
            pnSubscribed = False
            while flag:
                loopCount = loopCount + 1
                if loopCount >= 60:
                    flag = False
                    print ("Timeout after waiting for platform navigator subscription. Current time : ", time.asctime())
                    timeout = True
                    break # safe break after 1 hr
                if pnSubscribed == False:
                    res1 = runKubernetesCommand("get subscription ibm-integration-platform-navigator -o yaml", namespace, True, 0, False)
                    if res1 != None and res1 != "" and res1.lower().startswith("error") == False:
                        res1 = yaml.safe_load(res1)
                        if "status" in res1 and "conditions" in res1["status"]:
                            conditions = res1["status"]["conditions"]
                            for eachCondition in conditions:
                                if eachCondition["type"] == "CatalogSourcesUnhealthy" and eachCondition["status"] == "False":
                                    print("ACTION OUTPUT : Platform navigator is subscribed and ready.")
                                    pnSubscribed = True

                if pnSubscribed:
                    flag = False
                else:
                    print ("Waiting for platform navigator subscription to be ready. Current time : ", time.asctime())
                    time.sleep(60)
            
            if timeout:
                print (ERRORED_TIME_MESSAGE, time.asctime())
                sys.exit("ERROR : Timedout waiting for platform navigator subscription in namespace, {}. Manually check the status of PN subscription and try again.")

        pnInstanceName = None
        pnInstanceExists = False
        pn_instances = None
        count5 = 0
        if args.no_install == False:
            while True:
                count5 = count5 + 1
                if count5 > 60: 
                    sys.exit("Platform navigator and dependencies not ready. Timed out after 1 hour.")

                pn_instances = runKubernetesCommand("get platformnavigator", args.ns, False, 0, False)
                if pn_instances != None and pn_instances != "" and (pn_instances.lower().startswith("error") or "no matches for kind" in pn_instances.lower() or "error" in pn_instances.lower()):
                    print("Waiting for platform navigator and its dependencies to be ready..", time.asctime())
                    time.sleep(60)
                else:
                    break
        
        # create instance of PN
        #check if platform navigator instance exists
        #namespace will be same as what apic is will be installed.
        if pn_instances != None and pn_instances != "":
            pn_instances = pn_instances.splitlines()
            for eachPNInstance in pn_instances:
                if eachPNInstance.startswith("NAME"): continue
                pnInstanceName = eachPNInstance[0:eachPNInstance.index(" ")]
                pnInstance = runKubernetesCommand("get platformnavigator " + pnInstanceName + " -o yaml", args.ns)
                if pnInstance != None and pnInstance != "" and pnInstance.lower().startswith("error") == False:
                    pnInstance = yaml.safe_load(pnInstance)
                    if "spec" in pnInstance and "version" in pnInstance["spec"]:
                        version = pnInstance["spec"]["version"]
                        if version == cp4iVersion:
                            pnInstanceExists = True
                            print("ACTION OUTPUT : Platform navigator instance already exists for version, " + cp4iVersion + " Not installing again. Proceeding further.")
                            print()
                        else:
                            print (ERRORED_TIME_MESSAGE, time.asctime())
                            sys.exit("Platform navigator already exists for a different version, " + version + " Uninstall it and try again. This script uses version " + cp4iVersion)
        
        if pnInstanceExists == False:
            pn_instance_yaml["metadata"]["namespace"] = args.ns
            pn_instance_yaml["spec"]["license"]["license"] = args.license_pn
            # not needed from v10.0.7.0
            # pn_instance_yaml["spec"]["storage"]["class"] = args.storageclass_pn 
            createPNInstanceFileName = DATA_TEMP_DIR + "/pn_create_instance.yaml"
            with open(createPNInstanceFileName, 'w') as file2:
                yaml.dump(pn_instance_yaml, file2, default_flow_style=False)
            if args.no_install == False:
                pnInstanceName = pn_instance_yaml["metadata"]["name"]
                runKubernetesCommand("create -f " + createPNInstanceFileName, args.ns, False)
                time.sleep(60)
                print("ACTION OUTPUT : Created platform navigator instance.")
            else:
                print("no_install flag is set to true. Not installing platform navigator instance.")
                print("ACTION OUTPUT : Location of platform navigator instance creation yaml file : ", createPNInstanceFileName)
                print()
        
        # check if PN instance is created
        if args.no_install == False:
            flag = True
            loopCount = 0
            timeout = False
            pnInstanceCreated = False
            while flag:
                loopCount = loopCount + 1
                if loopCount >= 40:
                    flag = False
                    print ("Timeout after waiting for platform navigator instance. Current time : ", time.asctime())
                    timeout = True
                    break # safe break after 2 hr
                if pnInstanceCreated == False:
                    res1 = runKubernetesCommand("get platformnavigator " + pnInstanceName + " -o yaml", args.ns, True, 0, False)
                    if res1 != None and res1 != "" and res1.lower().startswith("error") == False:
                        res1 = yaml.safe_load(res1)
                        if "status" in res1 and "conditions" in res1["status"]:
                            conditions = res1["status"]["conditions"]
                            for eachCondition in conditions:
                                if eachCondition["type"] == "Ready" and eachCondition["status"] == "True":
                                    pnInstanceCreated = True
                
                if pnInstanceCreated:
                    flag = False
                else:
                    print ("Waiting for platform navigator instance to be ready. Current time : ", time.asctime())
                    time.sleep(180)
            
            if timeout:
                print (ERRORED_TIME_MESSAGE, time.asctime())
                sys.exit("ERROR : Timedout waiting for platform navigator instance in namespace, {}. Manually check the status of PN instance and try again.")
            
    print()
    print()

    #subscribe    
    apiconnect_subscribe["metadata"]["namespace"] = namespace
    datapower_subscribe["metadata"]["namespace"] = namespace

    #check if apiconnect and dp subscription exists
    subscriptions = runKubernetesCommand("get subscription", namespace, False)
    subscriptions = subscriptions.splitlines()
    apicSubscriptionExists = False
    dpSubscriptionExists = False
    for eachSubscription in subscriptions:
        if "datapower" in eachSubscription:
            dpSubscriptionName = eachSubscription[0:eachSubscription.index(" ")]
            dpSubscription = runKubernetesCommand("get subscription " + dpSubscriptionName + " -o yaml", namespace, True)
            dpSubscription = yaml.safe_load(dpSubscription)
            channel = dpSubscription["spec"]["channel"]
            if channel == dpChannel:
                dpSubscriptionExists = True
                print("ACTION OUTPUT : Datapower operator already subscribed for channel number, " + dpChannel + " Not installing again. Proceeding further.")
                print()
            else:
                print (ERRORED_TIME_MESSAGE, time.asctime())
                sys.exit("Datapower operator already subscribed for different channel number, " + channel + " Uninstall it and try again. This script uses Datapower channel " + dpChannel)
        
        if "apiconnect" in eachSubscription:
            apicSubscriptionName = eachSubscription[0:eachSubscription.index(" ")]
            apicSubscription = runKubernetesCommand("get subscription " + apicSubscriptionName + " -o yaml", namespace, True)
            apicSubscription = yaml.safe_load(apicSubscription)
            channel = apicSubscription["spec"]["channel"]
            if channel == apicChannel:
                apicSubscriptionExists = True
                print("ACTION OUTPUT : API Connect operator already subscribed for channel number, " + apicChannel + " Not installing again. Proceeding further.")
                print()
            else:
                print (ERRORED_TIME_MESSAGE, time.asctime())
                sys.exit("API Connect operator already subscribed for different channel number, " + channel + " Uninstall it and try again. This script uses API Connect channel " + apicChannel)
    
    if dpSubscriptionExists == False:
        if args.custom_build:
            datapower_subscribe["spec"]["source"] = "ibm-datapower-operator-catalog"
            
        subscribeDPFileName = DATA_TEMP_DIR + "/subscription_dp.yaml"
        with open(subscribeDPFileName, 'w') as file2:
            yaml.dump(datapower_subscribe, file2, default_flow_style=False)
        if args.no_install == False:
            runKubernetesCommand("create -f " + subscribeDPFileName, namespace, False)
            time.sleep(120)
            print("ACTION OUTPUT : Created Datapower subscription")
        else:
            print("no_install flag is set to true. Not installing datapower operator.")
            print("ACTION OUTPUT : Location of Datapower subscription file : ", subscribeDPFileName)
        print()

    if apicSubscriptionExists == False:
        if args.custom_build:
            apiconnect_subscribe["spec"]["source"] = "ibm-apiconnect-catalog"
            
        subscribeAPICFileName = DATA_TEMP_DIR + "/subscription_apic.yaml"
        with open(subscribeAPICFileName, 'w') as file2:
            yaml.dump(apiconnect_subscribe, file2, default_flow_style=False)
        if args.no_install == False:
            runKubernetesCommand("create -f " + subscribeAPICFileName, namespace, False)
            time.sleep(120)
            print("ACTION OUTPUT : Created APIC subscription")
        else:
            print("no_install flag is set to true. Not installing apic operator.")
            print("ACTION OUTPUT : Location of APIC subscription file : ", subscribeAPICFileName)
        print()
    
    if args.no_install == False:
        flag = True
        loopCount = 0
        timeout = False
        apicDeployed = False
        dpDeployed = False
        while flag:
            loopCount = loopCount + 1
            if loopCount >= 60:
                flag = False
                print ("Timeout after waiting for apic and datapower operators to get deployed. Current time : ", time.asctime())
                timeout = True
                break # safe break after 1 hr
            if apicDeployed == False:
                res1 = runKubernetesCommand("get deployment ibm-apiconnect", namespace, True, 0, False)
                if res1 != None and res1 != "" and res1.lower().startswith("error") == False:
                    res11 = res1.splitlines()
                    for each in res11:
                        if each.startswith("ibm-apiconnect") and "1/1" in each:
                            print("ACTION OUTPUT : API Connect deployment is ready. \n", res1)
                            apicDeployed = True
                            break
            if dpDeployed == False:
                res2 = runKubernetesCommand("get deployment datapower-operator", namespace, True, 0, False)
                if res2 != None and res2 != "" and res2.lower().startswith("error") == False:
                    res22 = res2.splitlines()
                    for each2 in res22:
                        if each2.startswith("datapower-operator") and "1/1" in each2:
                            print("ACTION OUTPUT : DataPower deployment is ready. \n", res2)
                            dpDeployed = True
                            break
            if apicDeployed and dpDeployed:
                flag = False
            else:
                print ("Waiting for apic and data power operators to be ready. Current time : ", time.asctime())
                time.sleep(60)
        
        if timeout:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR : Timedout waiting for apic and datapower operators to be deployed in namespace, {}. Manually check the status of installed operators and try again.")


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
                    print (ERRORED_TIME_MESSAGE, time.asctime())
                    sys.exit("ERROR : Invalid namespace, {} provided. Namespace(s) given as input for this subsystem : {}. Exiting...".format(each, eachGivenNS))


def validateInputs():   
    global mgmtSubsystemDetails
    global portalSubsystemDetails

    # for lts release and ocp version check
    if ltsRelease:
        validOCPVersion = False
        for eachSupportedOCPVersion in LTS_OCP_VERSIONS:
            if ocpVersion.startswith(eachSupportedOCPVersion):
                validOCPVersion = True
                break
        if validOCPVersion == False:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR :Extended Update Support (LTS) release is getting installed But the OCP version({}) is not valid for LTS release. Exiting...".format(ocpVersion))
    
    if args.license == None or args.license == "":
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("ERROR : Need license value for CD/LTS release being used. Refer https://www.ibm.com/docs/en/api-connect/10.0.x?topic=requirements-api-connect-licenses. Use -license flag. Exiting...".format(ocpVersion))

    #check if storageclass exists
    validStorageClasses = []
    storageclasses = runKubernetesCommand("get storageclass", args.ns, False)
    storageclasses = storageclasses.splitlines()
    for eachsc in storageclasses:
        validStorageClasses.append(eachsc[0:eachsc.index(" ")])
    print("Valid storage classes : ", validStorageClasses)
    
    if args.storageclass_apic == None or args.storageclass_apic not in validStorageClasses:
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("ERROR :Invalid storage class provided for APIC installation. use -storageclass_apic flag. Given value is {}. Exiting...".format(args.storageclass_apic))
        
    # if args.cp4i and (args.storageclass_pn == None or args.storageclass_pn not in validStorageClasses):
    #     print (ERRORED_TIME_MESSAGE, time.asctime())
    #    sys.exit("ERROR :Invalid storage class provided for platform navigator in CP4I installation. Given value is {}. Exiting...".format(args.storageclass_pn))
    
    if args.cp4i and (args.license_pn == None or args.license_pn == ""):
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("ERROR :Invalid license provided to install platform navigator instance. Given value is {}. Exiting...".format(args.license_pn))
    
    # check if block storage for apic and filesystem storage for pn as WELL. TBD
    
    #check if apic is installed or not
    getapic_out = runKubernetesCommand("get apiconnectcluster.apiconnect.ibm.com", args.ns, False, 0, False)
    if getapic_out.startswith("error") == False and len(getapic_out.splitlines()) > 1:
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("ERROR : Resource of type apiconnectcluster.apiconnect.ibm.com(top level CR) already exist in the namespace. Exiting...")
    
    getmgmt_out = runKubernetesCommand("get managementcluster.management.apiconnect.ibm.com", args.ns, False, 0, False)
    if getmgmt_out.startswith("error") == False and len(getmgmt_out.splitlines()) > 1:
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("ERROR : Resource of type managementcluster.management.apiconnect.ibm.com already exist in the namespace. Exiting...")

    if args.no_portal == False:
        getptl_out = runKubernetesCommand("get portalcluster.portal.apiconnect.ibm.com", args.ns, False, 0, False)
        if getptl_out.startswith("error") == False and len(getptl_out.splitlines()) > 1:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR : Resource of type portalcluster.portal.apiconnect.ibm.com already exist in the namespace. Exiting...")

    if args.no_gateway == False:
        getgw_out = runKubernetesCommand("get gatewaycluster.gateway.apiconnect.ibm.com", args.ns, False, 0, False)
        if getgw_out.startswith("error") == False and len(getgw_out.splitlines()) > 1:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR : Resource of type gatewaycluster.gateway.apiconnect.ibm.com already exist in the namespace. Exiting...")
 
    if args.no_analytics == False:
        geta7sout = runKubernetesCommand("get analyticscluster.analytics.apiconnect.ibm.com", args.ns, False, 0, False)
        if geta7sout.startswith("error") == False and len(geta7sout.splitlines()) > 1:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR : Resource of type analyticscluster.analytics.apiconnect.ibm.com already exist in the namespace. Exiting...")
    
    mgmtSubsystemNames = config["management_subsystem"].keys()
    selectedManagementSubsystem = None
    if len(mgmtSubsystemNames) > 1:
        print ()
        print ("List of management subsystems from the saved configuration(source system) : ", list(mgmtSubsystemNames))
        if args.silent:
            selectedManagementSubsystem = args.mgmt_subsystem_name
        else:
            selectedManagementSubsystem = input("SELECT THE SUBSYSTEM FROM THE LIST which you want to use for top level cr : ")
            
        if selectedManagementSubsystem != None: selectedManagementSubsystem = selectedManagementSubsystem.strip()
        if selectedManagementSubsystem not in config["management_subsystem"]:
            if args.silent and selectedManagementSubsystem == None:
                print("Multiple management subsystems found in the saved configuration. You need to select one by using -mgmt_subsys_name or --mgmt_subsystem_name flag")
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR : The selected subsystem({}) does not exist in the configuration. Exiting...".format(selectedManagementSubsystem))
    elif len(mgmtSubsystemNames) == 1:
        selectedManagementSubsystem = list(mgmtSubsystemNames)[0]
    

    if selectedManagementSubsystem != None and args.ns != None:
        mgmtSubsystemDetails = config["management_subsystem"][selectedManagementSubsystem]
        print ("selected management subsystem from the source configuration : ", selectedManagementSubsystem)
    else:
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("ERROR : Invalid management subsystem from source. Check values for source management subsystem name : {} and target namespace : {}".format(selectedManagementSubsystem, args.ns))
    
    versionReconciled = mgmtSubsystemDetails["versionReconciled"]
    if versionReconciled != None and versionReconciled.startswith("10."):
        if "customApplicationCredentials" in mgmtSubsystemDetails:
            customApplicationCredentials = mgmtSubsystemDetails["customApplicationCredentials"]
            for each in customApplicationCredentials:
                runKubernetesCommand("get secret " + each["secretName"], args.ns, False)
                if each["name"] in mgmtCustomApplicationSecrets:
                    mgmtCustomApplicationSecrets.remove(each["name"])
            
            if len(mgmtCustomApplicationSecrets) > 0:
                print (ERRORED_TIME_MESSAGE, time.asctime())
                sys.exit("ERROR : Exiting the script as some secrets from management customApplicationCredentials are missing in the configuration. Missing secrets : {}".format(mgmtCustomApplicationSecrets))
        else:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR : Not able to verify the secrets for customApplicationCredentials from source configuration.  customApplicationCredentials not present in source configuration. Exiting...")
    else:
        print ("ACTION OUTPUT : Not checking for customApplicationCredentials as they are not present as source version is ", versionReconciled)

    if "encryptionSecret" in mgmtSubsystemDetails and "secretName" in mgmtSubsystemDetails["encryptionSecret"]:
        mgmtEncryptionSecret = mgmtSubsystemDetails["encryptionSecret"]["secretName"]
        runKubernetesCommand("get secret " + mgmtEncryptionSecret, args.ns, False)
    else:
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("ERROR : Not able to verify the management encryption secret from source configuration. encryptionSecret not present in source configuration. Exiting...")

    if "databaseBackup" in mgmtSubsystemDetails and "credentials" in mgmtSubsystemDetails["databaseBackup"]:
        dbCredentialSecret = mgmtSubsystemDetails["databaseBackup"]["credentials"]
        runKubernetesCommand("get secret " + dbCredentialSecret, args.ns, False)
    else:
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("ERROR : Not able to verify database backup credential secret from source configuration. databaseBackup not present in source configuration. Exiting...")
    
    selectedPortalSubsystem = None
    if args.no_portal == False and config_portal != None:
        portalSubsystemNames = config_portal["portal_subsystem"].keys()
        if len(portalSubsystemNames) > 1:
            print ()
            print ("List of portal subsystems from the saved configuration(source system) : ", list(portalSubsystemNames))
            print ("Portal encryption secret and backup secret wil be used from this subsystem while creating top level cr.")
            if args.silent:
                selectedPortalSubsystem = args.ptl_subsystem_name
            else:
                selectedPortalSubsystem = input("SELECT THE SUBSYSTEM FROM THE LIST which you want to use for top level cr : ")
            
            if selectedPortalSubsystem != None: selectedPortalSubsystem = selectedPortalSubsystem.strip()
            if selectedPortalSubsystem not in config_portal["portal_subsystem"]:
                if args.silent and selectedPortalSubsystem == None:
                    print("Multiple portal subsystems found in the saved configuration. You need to select one by using -ptl_subsys_name or --ptl_subsystem_name flag")
                print (ERRORED_TIME_MESSAGE, time.asctime())
                sys.exit("ERROR : The selected subsystem({}) does not exist in the configuration. Exiting...".format(selectedPortalSubsystem))
                
        elif len(portalSubsystemNames) == 1:
            selectedPortalSubsystem = list(portalSubsystemNames)[0]
            
        if selectedPortalSubsystem != None and args.ns != None:
            portalSubsystemDetails = config_portal["portal_subsystem"][selectedPortalSubsystem]
            print ("selected portal subsystem from the source configuration : ", selectedPortalSubsystem)
        else:
            sys.exit ("ERROR : Invalid portal subsystem from source. Check values for source portal subsystem name : {} and target namespace : {}".format(selectedPortalSubsystem, args.ns))
        
        if "encryptionSecret" in portalSubsystemDetails and "secretName" in portalSubsystemDetails["encryptionSecret"]:
            ptlEncryptionSecret = portalSubsystemDetails["encryptionSecret"]["secretName"]
            runKubernetesCommand("get secret " + ptlEncryptionSecret, args.ns, False)
        else:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR : Not able to verify the portal encryption secret from source configuration. encryptionSecret not present in source configuration. Exiting...")

        if "portalBackup" in portalSubsystemDetails and "credentials" in portalSubsystemDetails["portalBackup"]:
            dbCredentialSecret = portalSubsystemDetails["portalBackup"]["credentials"]
            runKubernetesCommand("get secret " + dbCredentialSecret, args.ns, False)
        else:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR : Not able to verify portal backup credential secret from source configuration. portalBackup not present in source configuration. Exiting...")


def createTopLevelCR():
    global profiles
    print("Create top level CR::")

    topLevelCR["metadata"]["namespace"] = args.ns
    
    if args.name != None and args.name != "":
        topLevelCR["metadata"]["name"] = args.name
        topLevelCR["metadata"]["labels"]["app.kubernetes.io/name"] = args.name

    if args.production:
        topLevelCR["spec"]["license"]["use"] = "production"
    
    if args.license == None or args.license == "":
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("Invalid license value({}) provided in top level CR. Refer https://www.ibm.com/docs/en/api-connect/10.0.5.x_lts?topic=requirements-api-connect-licenses".format(args.license))
    topLevelCR["spec"]["license"]["license"] = args.license

    topLevelCR["spec"]["storageClassName"] = args.storageclass_apic
    
    topLevelCR["spec"]["version"] = apicVersion
    
    if args.profile != None and args.profile != "":
        if args.no_gateway:
            profiles = profiles + ADDITIONAL_PROFILES_IF_REMOTE_GATEWAY
        if args.profile not in profiles:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("Invalid profile value({}) provided in top level CR, supported profile values :{}".format(args.profile, profiles))
        topLevelCR["spec"]["profile"] = args.profile
    else:
        topLevelCR["spec"]["profile"] = profiles[0]
    
    versionReconciled = mgmtSubsystemDetails["versionReconciled"]

    topLevelCR["spec"]["management"]["encryptionSecret"] = mgmtSubsystemDetails["encryptionSecret"]
    topLevelCR["spec"]["management"]["databaseBackup"] = mgmtSubsystemDetails["databaseBackup"]

    #https://github.ibm.com/velox/platform/issues/7555
    if (versionReconciled != None and versionReconciled.startswith("10.")) and ("databaseBackup" in mgmtSubsystemDetails and "protocol" in mgmtSubsystemDetails["databaseBackup"] and mgmtSubsystemDetails["databaseBackup"]["protocol"] == "objstore"):
        #only if s3 backup and if v10 DR. For v2018 to v10 FFM, we use different new s3 backup path
        topLevelCR["metadata"]["annotations"] = {
            "apiconnect-operator/deployment-mode": "disasterRecovery"
        }
    
    if versionReconciled != None and versionReconciled.startswith("10."):
        topLevelCR["spec"]["management"]["name"] = mgmtSubsystemDetails["name"]
        topLevelCR["spec"]["management"]["originalUID"] = mgmtSubsystemDetails["originalUID"]
        topLevelCR["spec"]["management"]["customApplicationCredentials"] = mgmtSubsystemDetails["customApplicationCredentials"]
        topLevelCR["spec"]["management"]["siteName"] = mgmtSubsystemDetails["siteName"]
    else:
        del topLevelCR["spec"]["management"]["name"]
        del topLevelCR["spec"]["management"]["originalUID"]
        del topLevelCR["spec"]["management"]["siteName"]
    
    if args.no_portal:
        del topLevelCR["spec"]["portal"]
        if "disabledServices" in topLevelCR["spec"]:
            topLevelCR["spec"]["disabledServices"].append("portal")
        else:
            topLevelCR["spec"]["disabledServices"] = ["portal"]
    else:
        if portalSubsystemDetails != None:
            #name from source not really needed for portal during dr
            if "portal" in topLevelCR["spec"] and "name" in topLevelCR["spec"]["portal"]:
                del topLevelCR["spec"]["portal"]["name"] # remove default value
            #topLevelCR["spec"]["portal"]["name"] = portalSubsystemDetails["name"]

            topLevelCR["spec"]["portal"]["encryptionSecret"] = portalSubsystemDetails["encryptionSecret"]
            topLevelCR["spec"]["portal"]["portalBackup"] = portalSubsystemDetails["portalBackup"]

            if versionReconciled != None and versionReconciled.startswith("10."):
                topLevelCR["spec"]["portal"]["originalUID"] = portalSubsystemDetails["originalUID"]
                topLevelCR["spec"]["portal"]["siteName"] = portalSubsystemDetails["siteName"]
            else:
                del topLevelCR["spec"]["portal"]["originalUID"]
                del topLevelCR["spec"]["portal"]["siteName"]
        else:
            del topLevelCR["spec"]["portal"]

    if args.no_analytics:
        del topLevelCR["spec"]["analytics"]
        if "disabledServices" in topLevelCR["spec"]:
            topLevelCR["spec"]["disabledServices"].append("analytics")
        else:
            topLevelCR["spec"]["disabledServices"] = ["analytics"]
    
    if args.no_gateway:
        if "disabledServices" in topLevelCR["spec"]:
            topLevelCR["spec"]["disabledServices"].append("gateway")
        else:
            topLevelCR["spec"]["disabledServices"] = ["gateway"]
    
    topLevelCRFileName = DATA_DIR + "/top_level_cr.yaml"
    with open(topLevelCRFileName, 'w') as topCRFile:
            yaml.dump(topLevelCR, topCRFile, default_flow_style=False)
    
    if args.no_install == False:
        print("Location of API Connect top level CR file : ", topLevelCRFileName)
        runKubernetesCommand("create -f " + topLevelCRFileName, args.ns, False, 50)
        time.sleep(30)

    else:
        print("no_install flag is set to true. Not installing API Connect.")
        print("Location of API Connect top level CR file : ", topLevelCRFileName)

    if args.no_install == False:
        flag = True
        loopCount = 0
        timeout = False
        apicInstalled = False
        while flag:
            loopCount = loopCount + 1
            if loopCount >= 50:
                flag = False
                print ("Timeout after waiting for APIC instance creation. Current time : ", time.asctime())
                timeout = True
                break # safe break after 2.5 hr
            if apicInstalled == False:
                res1 = runKubernetesCommand("get apiconnectcluster.apiconnect.ibm.com " + topLevelCR["metadata"]["name"] + " -o yaml", args.ns, True, 0, False)
                if res1 != None and res1 != "" and res1.lower().startswith("error") == False:
                    res1 = yaml.safe_load(res1)
                    if "status" in res1 and "conditions" in res1["status"]:
                        conditions = res1["status"]["conditions"]
                        for eachCondition in conditions:
                            if eachCondition["type"] == "Ready" and eachCondition["status"] == "True":
                                apicInstalled = True
            
            if apicInstalled:
                flag = False
            else:
                print ("Waiting for APIC instance to be ready. Current time : ", time.asctime())
                time.sleep(180)
        
        if timeout:
            print (ERRORED_TIME_MESSAGE, time.asctime())
            sys.exit("ERROR : Timedout waiting for APIC instance in namespace, {}. Manually check the status of APIC instance.")
    
    #versionReconciled = mgmtSubsystemDetails["versionReconciled"]
    #if versionReconciled != None and versionReconciled.startswith("2018."):
    #    runKubernetesCommand("adm policy add-scc-to-user anyuid system:serviceaccount:" + args.ns + ":default", None)

    print()
    print("This script performed the following actions in the target cluster:")
    print("**********************************************************************")
    if args.cp4i and args.no_install == False:
        print("- Installed Platform Navigator and created an instance of it.")
    if args.no_install:
        print("- Generated the yamls for catalog sources, subscriptions and top level CR. Check the data directory and data/temp directory.")
    else:
        print("- Using the saved configuration from source system, installed API Connect on the target cluster.")
    print()
    print("Next steps:")
    print("1. Restore management backup by running the script, restore_management_db.py")
    print()
        

    

# start
def start():
    global ocpVersion
    
    print ("CHECKING IF KUBECTL/OC EXIST IN THE PATH AND HAVE ACCESS TO THE CLUSTER :")
    ocpVersion = runKubernetesCommand("version", "default", False)
    ocpVersion = ocpVersion.splitlines()
    for each in ocpVersion:
        if each.startswith("Server"):
            ocpVersion = each[each.index(":")+1:].strip()
            break

    if args.skip_namespace_validation == False:
        validateNamespaces([args.ns])
    
    if args.ns == None or args.ns == "" or "|" in args.ns:
        print (ERRORED_TIME_MESSAGE, time.asctime())
        sys.exit("ERROR : Invalid namespace({}) provided to install target APIC system. Only one namespace need to be provided. Exiting...".format(args.ns))

    validateInputs()
    install_catalog_sources_and_subscribe()
    time.sleep(30)
    createTopLevelCR()
    
	
parser = argparse.ArgumentParser(description="The script is used in form factor to form factor migration to install the target API Connect system on Openshift Cloud Platform.\n\
The latest version of the  Long Term Support (LTS) or Continuous Delivery (CD) is installed.\n\
It does not support installation of API Connect on Kubernetes or VMWare appliance.\n \n\
Prerequisites ::\n\
1. Access to the OCP cluster using oc command,\n\
2. Python 3.x and PyYAML module need to be installed\n\
3. This script must be run on supported version of the OCP cluster.\n\
4. The entitlement key to pull the images from IBM Container Registry or other registry must be already added to the OCP cluster or the images must be already be available in the registry.\n\
5. The storageclasses needed for API Connect and platform navigator must already be created on the OCP cluster.\n\
6. The data directory where the configuration from the source system are saved. The data directory with source configuration must be present in the same directory as this script." , 
formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument("-n", "--namespace", dest = "ns", help="Uses this namespace to install API Connect.")
parser.add_argument("-operator_in_specific_namespace", "--operator_in_specific_namespace", action='store_true', dest = "operator_in_specific_namespace", help="Operators (APIC operator, Datapower operator, common services operator, platform navigator) will be installed in same namespace where API Connect will be installed. If not provided, default is all namespaces")

parser.add_argument("-production", "--production", action='store_true', dest = "production", help="License use is set to production. If not provided defaulted to nonproduction.")
parser.add_argument("-license", "--license", dest = "license", help="License value when using CD release. Refer https://www.ibm.com/docs/en/api-connect/10.0.x?topic=requirements-api-connect-licenses")
parser.add_argument("-name", "--name", dest = "name", help="Name of the top level CR. If not provided defaulted to minimum.")
parser.add_argument("-profile", "--profile", dest = "profile", help="profile value for the top level cr. If not provided defaulting to " + profiles[0])
parser.add_argument("-cp4i", "--cp4i",  action='store_true', dest = "cp4i", help="It is Cloud Pak for Integration. APIC and Platform navigator will be installed.")

parser.add_argument("-storageclass_apic", "--storageclass_apic", dest = "storageclass_apic", help="Storage class used by API Connect.")
parser.add_argument("-storageclass_pn", "--storageclass_pn", dest = "storageclass_pn", help="Storage class used by platform navigator in case of Cloud Pak for Integration. This is NOT needed from v1.0.7.0")
parser.add_argument("-license_pn", "--license_pn", dest = "license_pn", help="License for platform navigator instance.")

parser.add_argument('-skip_namespace_validation', "--skip_namespace_validation",  action='store_true', dest = "skip_namespace_validation", help='Skips validation of input namespaces.')

parser.add_argument("-no_portal", "--no_portal", action='store_true', dest = "no_portal", help="Portal subsystem will not be installed")
parser.add_argument("-no_gateway", "--no_gateway", action='store_true', dest = "no_gateway", help="Gateway subsystem will not be installed")
parser.add_argument("-no_analytics", "--no_analytics", action='store_true', dest = "no_analytics", help="Analytics subsystem will not be installed")

parser.add_argument('-mgmt_subsys_name', "--mgmt_subsystem_name", dest = "mgmt_subsystem_name", help='If multiple management subsytems present in the configuration, the script will use this.')
parser.add_argument('-ptl_subsys_name', "--ptl_subsystem_name", dest = "ptl_subsystem_name", help='If multiple portal subsytems present in the configuration, the script will use this.')
parser.add_argument('-silent', "--silent", action='store_true', dest = "silent", help='Does not prompt for additinal inputs and proceeds silently.')

parser.add_argument("-custom_build", "--custom_build",  action='store_true', dest = "custom_build", help="Indicates custom build during development or a fix.")
parser.add_argument("-apic_catsrc_image", "--apic_catsrc_image", dest = "apic_catsrc_image", help="Custom build image value for API Connect catalog source. Mandatory if -custom_build being used.")
parser.add_argument("-dp_catsrc_image", "--dp_catsrc_image", dest = "dp_catsrc_image", help="Custom build image value for Datapower catalog source. Mandatory if -custom_build being used.")
parser.add_argument("-pn_catsrc_image", "--pn_catsrc_image", dest = "pn_catsrc_image", help="When using -custom_build option, platform navigator catalog source image value. This is optional and defaulted to cp.stg.icr.io/cp/ibm-integration-platform-navigator-catalog:latest-cd if not provided.")

parser.add_argument("-no_install", "--no_install", action='store_true', dest = "no_install", help="Vaidates the configuration and creates the yaml for top level CR. Does not install operators or API Connect.")

parser.add_argument("-cert_manager_type", "--cert_manager_type", dest = "cert_manager_type", help="cert manager type. Supported values are ibm, redhat, other. If not provided, will default to value of the variable, DEFAULT_CERT_MANAGER_TYPE")
parser.add_argument("-cert_manager_channel", "--cert_manager_channel", dest = "cert_manager_channel", help="Channel version of the cert manager. Correct value need to be provided based on the cert manager type being used. If not provided, will default to one of the value of the variables, DEFAULT_IBM_CERT_MANAGER_CHANNEL / DEFAULT_REDHAT_CERT_MANAGER_CHANNEL based on the cert manager type being used.")
parser.add_argument("-cert_manager_operator_namespace", "--cert_manager_operator_namespace", dest = "cert_manager_operator_namespace", help="Namespace where cert manager operator is installed. Its optional and if not provided recommneded namespace is used for cert manager operator. For redhat cert manager, the supported namespaces are cert-manager-operator(recommended) or any custom namespace. For IBM cert manager the supported namespaces are ibm-cert-manager(recommended), custom namespace. Use this flag only if need to use custom namespace for cert manager operator and you know what you are doing.")
parser.add_argument("-common_services_channel", "--common_services_channel", dest = "common_services_channel", help="Channel version of common services. If not provided, will default to value of the variable, DEFAULT_COMMON_SERVICES_CHANNEL")
args = parser.parse_args()

print ("Start time :", time.asctime())
print ()

print ("Input namespace where API Connect is installed (-n or --namespace flag) : ", args.ns)
print ("Operators will be installed in the namespace given as input (NOT in all namespaces which is default) : ", args.operator_in_specific_namespace)
print ()

print ("Production installation (-production or --production flag) : ", args.production)
print ("License value being used (-license or --license flag) : ", args.license)
print ("Name of the top level CR (-name or --name flag) : ", args.name)
print ("Profile being installed by the top level CR (-profile or --profile flag) : ", args.profile)
print ("is CP4I installation (-cp4i or --cp4i flag) : ", args.cp4i)
print ()

print ("Storage class used by API Connect (-storageclass_apic or --storageclass_apic flag) : ", args.storageclass_apic)
if args.cp4i:
    print ("Storage class used by platform navigator instance (-storageclass_pn or --storageclass_pn flag) : ", args.storageclass_pn)
    print ("License value for platform navigator instance (-license_pn or --license_pn flag) : ", args.license_pn)
print ()

print ("Do not install portal subsystem (-no_portal or --no_portal flag) : ", args.no_portal)
print ("Do not install gateway subsystem (-no_gateway or --no_gateway flag) : ", args.no_gateway)
print ("Do not install analytics subsystem (-no_analytics or --no_analytics flag) : ", args.no_analytics)
print ()

print ("Installation using custom build (-custom_build or --custom_build flag) : ", args.custom_build)
print ("Custom build apiconnect catalog source image value (-apic_catsrc_image or --apic_catsrc_image flag) : ", args.apic_catsrc_image)
print ("Custom build datapower catalog source image value (-dp_catsrc_image or --dp_catsrc_image flag) : ", args.dp_catsrc_image)
print ("Custom build platform navigator catalog source image value (-pn_catsrc_image or --pn_catsrc_image flag) : ", args.pn_catsrc_image)
print ()
print ("Just generate the yaml files and do not install API Connect: ", args.no_install)
print ()
print ("Common services channel (-common_services_channel or --common_services_channel): ", args.common_services_channel)
print ("Cert manager type (-cert_manager_type or --cert_manager_type): ", args.cert_manager_type)
print ("Cert manager channel (-cert_manager_channel or --cert_manager_channel): ", args.cert_manager_channel)

print ("Mangement subsystem name (-mgmt_subsys_name or --mgmt_subsystem_name flag) : ", args.mgmt_subsystem_name)
print ("Portal subsystem name (-ptl_subsys_name or --ptl_subsystem_name flag) : ", args.ptl_subsystem_name)
print ("silent (-silent or --silent flag) : ", args.silent)
print ()

pwd = os.getcwd()
DATA_DIR = pwd + "/data"
DATA_TEMP_DIR = pwd + "/data/temp"

if args.ns == None or args.ns == "":
    print (ERRORED_TIME_MESSAGE, time.asctime())
    sys.exit ("ERROR : Namespace (-n or --namespace flag) where API Connect need to be installed is not provided. Exiting...")


# load config data if exists
if os.path.exists(DATA_DIR + "/" + CONFIG_FILE_NAME):
    print ("Source APIC system configuration file exists. Loading it")
    text_file = open(DATA_DIR + "/" + CONFIG_FILE_NAME, "r")
    config1 = text_file.read()
    print("Configuration file : ", config1)
    config = yaml.safe_load(config1)
    text_file.close()
else:
    print (ERRORED_TIME_MESSAGE, time.asctime())
    sys.exit("ERROR : config.yaml file with details of the source APIC system in NOT present in the data directory. Exiting...")
    
# load portal config data if exists
if args.no_portal == False:
    if os.path.exists(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME):
        print ("Source APIC system portal configuration file exists. Loading it")
        text_file = open(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME, "r")
        config1 = text_file.read()
        print("portal configuration file : ", config1)
        config_portal = yaml.safe_load(config1)
        text_file.close()
    else:
        print("ACTION OUTPUT : No portal configuration found in the saved configuration of the source system")
        print()
        #print (ERRORED_TIME_MESSAGE, time.asctime())
        #sys.exit("ERROR : portal_config.yaml file with details of the source APIC system portal configuration in NOT present in the data directory. Exiting...")

start()

print()
print ("End time :", time.asctime())
