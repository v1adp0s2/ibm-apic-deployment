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
import random
from urllib.parse import urlparse


oc_client = "oc"
kubectl_client = "kubectl"
client = oc_client

pwd = None
DATA_DIR = None
DATA_TEMP_DIR = None
CONFIG_FILE_NAME = "config.yaml"
config =  None
cloudAdminServer = None
providerOrgServer = None
forceLogPasswords = None

managementSubsystemName = None

PORG_CREDENTIALS_FILE_NAME = "provider_org_credentials.yaml"
porg_credentials =  None
skipPOrgsWithMissingCredentials = False

migration_ur_name = "migrationur"
migration_ur_url = None
migration_user_name = "muser1"
migration_user_url = None
migrationUserPw = "m1gr@t10nUser"
migrationUserRealm = "provider/migrationur"

addPortalInfoInCatalogSettingRequest = {
  "portal": {
    "endpoint": "val",
    "portal_service_url": "val",
    "type": "drupal"
  },
  "application_lifecycle": {}
}

updateLegacyVanityEndpointsRequest = {
  "legacy_endpoint_behavior": "enabled",
  "v5_endpoint_substitution_behavior": {
    "base_endpoints": [],
    "unenforced_api_base_endpoint": None
  },
  "application_lifecycle": {},
  "vanity_api_endpoint": {
    "enabled": False
  }
}

targetSystemSpecVersion = None
targetSystemReconciledVersion = None

GATEWAY_PORTAL_MAPPING_FILENAME = "gateway_portal_mapping.yaml"
gateway_portal_mapping = None

apic_resources1 = {
  "configured-gateway-services": {
    "field_name": "configured-gateway-service",
    "additional_params_for_get": " --scope catalog",
    "additional_params_for_list": " --scope catalog",
    "global-policies": {
      "additional_params_for_get": " --scope catalog",
      "additional_params_for_list": " --format yaml --scope catalog",
      "methods": ["list-all"]
    },
    "global-policy-prehooks": {
      "additional_params_for_get": " --scope catalog",
      "methods": ["get"]
    },
    "global-policy-posthooks": {
      "additional_params_for_get": " --scope catalog",
      "methods": ["get"]
    },
    "global-policy-errors": {
      "additional_params_for_get": " --scope catalog",
      "methods": ["get"]
    },
    "policies": {
      "additional_params_for_get": " --scope catalog",
      "additional_params_for_list": " --format yaml --scope catalog",
      "methods": ["list-all"]
    },
    "extensions": {
      "additional_params_for_get": " --scope catalog",
      "additional_params_for_list": " --format yaml --scope catalog",
      "methods": ["list-all"]
    }
  },
  "products": {
    "additional_params_for_get": " --scope catalog",
    "additional_params_for_list": " --format yaml --scope catalog",
    "methods": ["list-all"]
  }
}

#space scope
apic_resources2 = {
  "configured-gateway-services": {
    "field_name": "configured-gateway-service",
    "additional_params_for_get": " --scope space",
    "additional_params_for_list": " --scope space",
    "global-policies": {
      "additional_params_for_get": " --scope space",
      "additional_params_for_list": " --format yaml --scope space",
      "methods": ["list-all"]
    },
    "global-policy-prehooks": {
      "additional_params_for_get": " --scope space",
      "methods": ["get"]
    },
    "global-policy-posthooks": {
      "additional_params_for_get": " --scope space",
      "methods": ["get"]
    },
    "global-policy-errors": {
      "additional_params_for_get": " --scope space",
      "methods": ["get"]
    },
    "policies": {
      "additional_params_for_get": " --scope space",
      "additional_params_for_list": " --format yaml --scope space",
      "methods": ["list-all"]
    },
    "extensions": {
      "additional_params_for_get": " --scope space",
      "additional_params_for_list": " --format yaml --scope space",
      "methods": ["list-all"]
    }
  },
  "products": {
    "additional_params_for_get": " --scope space",
    "additional_params_for_list": " --format yaml --scope space",
    "methods": ["list-all"]
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


def createMigrationUserData():
    global migration_ur_url
    global migration_user_url
    if os.path.exists(DATA_TEMP_DIR + "/" + "lur.yaml"):
        os.remove(DATA_TEMP_DIR + "/" + "lur.yaml")
    lurIntegrationTypeURL = runCommand("apic integrations:get --subcollection user-registry --fields name,title,url --server " + cloudAdminServer +" lur --output " + DATA_TEMP_DIR, True)
    lurIntegrationTypeURL = lurIntegrationTypeURL[lurIntegrationTypeURL.index("https://"):].strip()

    userRegistries = runCommand("apic user-registries:list --fields name,url --org admin --server " + cloudAdminServer, True)
    userRegistries = yaml.safe_load(userRegistries)
    migrationURExists = False
    for eachUR in userRegistries["results"]:
        if eachUR["name"] == migration_ur_name:
            migrationURExists = True
            migration_ur_url = eachUR["url"]
            break
    if migrationURExists == False:
        #create user registry
        urCreateRequest = {
            "case_sensitive": False,
            "email_unique_if_exist": True,
            "email_required": False,
            "title": migration_ur_name,
            "name": migration_ur_name,
            "visibility": {
                "type": "private"
            },
            "identity_providers": [
            {
                "title": migration_ur_name,
                "name": migration_ur_name
            }],
            "registry_type": "lur",
            "integration_url": lurIntegrationTypeURL
        }
        urCreateRequestFilename = DATA_TEMP_DIR + "/urCreateRequest.yaml"
        with open(urCreateRequestFilename, 'w') as f5:
            yaml.dump(urCreateRequest, f5, default_flow_style=False)
        createURResponse = runCommand("apic user-registries:create --org admin --server " + cloudAdminServer + " " + urCreateRequestFilename, True)
        createURResponse = createURResponse.strip()
        migration_ur_url = createURResponse[createURResponse.index("https://"):]
        print ("ACTION OUTPUT : Migration user registry created. Details : {}".format(createURResponse))
    else:
        print ("ACTION OUTPUT : Migration user registry already exists. User registry name : ", migration_ur_name)

    print()
    print()
    if os.path.exists(DATA_TEMP_DIR + "/" + migration_user_name + ".yaml"):
        os.remove(DATA_TEMP_DIR + "/" + migration_user_name + ".yaml")

    users = runCommand("apic users:list --fields name,url --org admin --server " + cloudAdminServer + " --user-registry " + migration_ur_name, True)
    users = yaml.safe_load(users)
    migrationUserExists = False
    for eachUser in users["results"]:
        if eachUser["name"] == migration_user_name:
            migrationUserExists = True
            migration_user_url = eachUser["url"]
            break
    
    if migrationUserExists == False:
        userCreateRequest = {
            "username": migration_user_name,
            "email": migration_user_name + "@test.com",
            "first_name": "Migration",
            "last_name": "User1",
            "password": migrationUserPw
        }
        userCreateFileName = DATA_TEMP_DIR + "/userCreateRequest.yaml"
        with open(userCreateFileName, 'w') as f6:
            yaml.dump(userCreateRequest, f6, default_flow_style=False)
        user = runCommand("apic users:create --org admin --server " + cloudAdminServer + " --user-registry " + migration_ur_name + " " + userCreateFileName, True)
        print ("ACTION OUTPUT : Migration user created. Details : {}".format(user))
        user = user.strip()
        migration_user_url = user[user.index("https://"):]
    else:
        print ("ACTION OUTPUT : Migration user already exists. Details : ", migration_user_url)


    print()
    print("ACTION OUTPUT : Migration user registry url : ", migration_ur_url)
    print("ACTION OUTPUT : Migration user url : ", migration_user_url)
    print()

    #add the migration user registry to API Manager
    fname = DATA_TEMP_DIR + "/UserRegistrySetting.yaml"
    if os.path.exists(fname):
        os.remove(fname)
    urSetting = runCommand("apic user-registry-settings:get --fields provider_user_registry_urls --server " + cloudAdminServer + " --output " + DATA_TEMP_DIR, False)
    urSetting = urSetting.strip()
    urSettingFileName = urSetting[urSetting.index("/"):]
    if os.path.exists(urSettingFileName):
        text_file = open(urSettingFileName, "r")
        config1 = text_file.read()
        urSetting = yaml.safe_load(config1)
        text_file.close()
    else:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : UserRegistrySetting.yaml file NOT found. Exiting...")
    if "provider_user_registry_urls" in urSetting and migration_ur_url not in urSetting["provider_user_registry_urls"]:
        print("ACTION OUTPUT : Adding migration user registry to API Manager cloud settings.")
        urSetting["provider_user_registry_urls"].append(migration_ur_url)
        with open(fname, 'w') as f1:
            yaml.dump(urSetting, f1, default_flow_style=False)
        runCommand("apic user-registry-settings:update --server " + cloudAdminServer + " " + fname)
    print()


def deleteMigrationUserData():
    fname = DATA_TEMP_DIR + "/UserRegistrySetting.yaml"
    if os.path.exists(fname):
        os.remove(fname)
    urSetting = runCommand("apic user-registry-settings:get --fields provider_user_registry_urls --server " + cloudAdminServer + " --output " + DATA_TEMP_DIR, False)
    urSetting = urSetting.strip()
    urSettingFileName = urSetting[urSetting.index("/"):]
    print("urSettingFileName : ", urSettingFileName)
    
    if os.path.exists(urSettingFileName):
        text_file = open(urSettingFileName, "r")
        config1 = text_file.read()
        urSetting = yaml.safe_load(config1)
        text_file.close()
    else:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : UserRegistrySetting.yaml file NOT found. Exiting...")
    print("UR setting : ", urSetting)
    print("migration ur url : ", migration_ur_url)
    print()

    if "provider_user_registry_urls" in urSetting:
        urSetting["provider_user_registry_urls"].remove(migration_ur_url)
        with open(fname, 'w') as f1:
            yaml.dump(urSetting, f1, default_flow_style=False)
        runCommand("apic user-registry-settings:update --server " + cloudAdminServer + " " + fname)

    res1 = runCommand("apic user-registries:delete --org admin --server " + cloudAdminServer + " " + migration_ur_name, True)
    print("ACTION OUTPUT : Deleted migration user registry, Details : ", res1)
    print()



def changeOwnerForProviderOrgs(toMigrationUser):
    porgs = runCommand("apic orgs:list --org_type=provider --fields name,owner_url --server " + cloudAdminServer, True)
    porgs = yaml.safe_load(porgs)
    if toMigrationUser:
        print("Set migration user as the owner for all provider orgs::")
        porgOwnersFilename = DATA_DIR + "/" + managementSubsystemName + "/porg_owners.yaml"
        if os.path.exists(porgOwnersFilename) == False:
            porg_owners = {}
            for eachOrg in porgs["results"]:
                porg_owners[eachOrg["name"]] = eachOrg["owner_url"]

            #save the original owners of all porgs
            with open(porgOwnersFilename, 'w') as f3:
                yaml.dump(porg_owners, f3, default_flow_style=False)

        changeOwnerToMigrationUser = {
            "new_owner_user_url": migration_user_url
        }
        fname = DATA_TEMP_DIR + "/changeOwnerToMigrationUser.yaml"
        with open(fname, 'w') as f1:
            yaml.dump(changeOwnerToMigrationUser, f1, default_flow_style=False)

        for eachOrg in porgs["results"]:
            runCommand("apic orgs:transfer-owner --server " + cloudAdminServer + " " + eachOrg["name"] + " " + fname, True)
            print("ACTION OUTPUT : Changed the owner to migration user for provider org, ", eachOrg["name"])
            print()
    else:
        print("Set to the original owners for all provider orgs::")
        porgOwnersFilename = DATA_DIR + "/" + managementSubsystemName + "/porg_owners.yaml"
        porg_owners = {}
        if os.path.exists(porgOwnersFilename):
            text_file2 = open(porgOwnersFilename, "r")
            config2 = text_file2.read()
            porg_owners = yaml.safe_load(config2)
            text_file2.close()
        else:
            print ("Time when error occurred :", time.asctime())
            sys.exit("ERROR : File containing the provider org owners NOT found. Exiting. File name : {}".format(porgOwnersFilename))
        for eachOrg in porgs["results"]:
            changeOwnerBackToOriginal = {
                "new_owner_user_url": porg_owners[eachOrg["name"]]
            }
            fname = DATA_TEMP_DIR + "/changeOwnerFor_" + eachOrg["name"] + "_request.yaml"
            with open(fname, 'w') as f1:
                yaml.dump(changeOwnerBackToOriginal, f1, default_flow_style=False)
            #delete_old_owner MUST be used only in this conditon so that the migration members gets deleted after transferring the ownership to the original one
            runCommand("apic orgs:transfer-owner --delete_old_owner --server " + cloudAdminServer + " " + eachOrg["name"] + " " + fname, True)
            print("ACTION OUTPUT : Changed to original owner for provider org, ", eachOrg["name"])
            print()
    print()


def updateGatewayInfoInManagementDB():
    global providerOrgServer
    global managementSubsystemName
    #get the saved configuration
    mgmtSubsystemNames = config["management_subsystem"].keys()
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
    else:
        print()
        managementSubsystemName = selectedSubsystem
        print ("selected management subsystem from the source configuration : ", managementSubsystemName)
        print()
        managementSubsystemDetails = config["management_subsystem"][managementSubsystemName]
        
        sourceSystemReconciledVersion = managementSubsystemDetails["versionReconciled"]
        print ("Source system version : {} and target system version : {}".format(sourceSystemReconciledVersion, targetSystemReconciledVersion))
        print()
        if args.ignore_version_check == False and targetSystemReconciledVersion != None and sourceSystemReconciledVersion.startswith("2018.") == False:
            if sourceSystemReconciledVersion.index("-") > 0:
                version1 = sourceSystemReconciledVersion[0:sourceSystemReconciledVersion.index("-")]
                if targetSystemReconciledVersion.startswith(version1) == False:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Target system version({}) does not match the soure system version({}).  Exiting...".format(targetSystemReconciledVersion, sourceSystemReconciledVersion))


        if "registered_gateways" not in managementSubsystemDetails:
            print ("ACTION OUTPUT : No gateways are registered in the management subsystem of the source system. No migration is needed. Exiting...")
            print ("Current time :", time.asctime())
            sys.exit(1)
        
        gatewaysFromSouceSystem = managementSubsystemDetails["registered_gateways"]
        
        #old_gw_endpoint : new_gateway_endpoint
        gatewayEndpointMap = {}
        #old_gw_endpoint^old_gw_api_endpoint_base : new_gateway_api_endpoint_base
        gatewayAPIEndpointBaseMap = {}
        print()
        print()
        
        i = 1
        print ("Checking the gateway instances(from the source system) saved in the data directory")
        print ("*********************************************************************************")
        for key in gatewaysFromSouceSystem:
            eachGW = gatewaysFromSouceSystem[key]
            print(str(i) + ". Checking the gateway instance(saved in config file) from the source system with NAME : {}, ENDPOINT : {}, API_ENDPOINT_BASE : {} ".format(eachGW["name"], eachGW["endpoint"], eachGW["api_endpoint_base"]))  
            i = i + 1
            if "NEW_ENDPOINT" in eachGW and "NEW_URL" in eachGW:
                print("NEW GATEWAY INSTANCE MATCHING ONE OF THE SOURCE SYSTEM GATEWAY. New gateway with NAME : {} , ENDPOINT : {}, API_ENDPOINT_BASE : {}".format(eachGW["NEW_NAME"], eachGW["NEW_ENDPOINT"], eachGW["NEW_API_ENDPOINT_BASE"])) 
                gatewayEndpointMap[eachGW["endpoint"]] = eachGW["NEW_ENDPOINT"]
                gatewayAPIEndpointBaseMap[eachGW["endpoint"] + "^" + eachGW["api_endpoint_base"]] = eachGW["NEW_API_ENDPOINT_BASE"]
            else:
                print ("NEW GATEWAY INSTANCE IS 'NOT' PRESENT IN THE CONFIGURATION for this source system gateway.")
        print()
        print()
        
        
        print ("Checking the gateway instances(in the target system) cloud manager database")
        print ("**************************************************************************")
        gatewayServicesInTargetDB = getGatewayServices(False)
        i = 1
        for key1 in gatewayServicesInTargetDB:
            val = gatewayServicesInTargetDB[key1].split("|")
            # not a old endpoint which is mapped already, not a already mapped new endpoint, endpoint not present in source system
            # basically found a new gateway which is not mapped and not present in the source system
            if key1 not in gatewayEndpointMap and key1 not in gatewayEndpointMap.values() and key1 not in gatewaysFromSouceSystem:
                print (str(i) + ". NEW gateway with ID : {}, TITLE : {}, API_ENDPOINT_BASE : {} and ENDPOINT : {} FOUND".format(val[0], val[1], val[2], key1))
                print ("If this gateway represents a new gateway instance in the target system and this is going to replace a old gateway endpoint, enter the corrosponding old gateway ENDPOINT that need to replaced")
                print ("If this gateway in target system DOES NOT replace any old gateway ENDPOINT, just press enter and proceed")
                oldGatewayEndpoint = input("ENTER THE 'OLD GATEWAY ENDPOINT' WHICH WILL BE REPLACED BY ABOVE, must start with https://    : ")
                print()
                i = i + 1
                if oldGatewayEndpoint != None: oldGatewayEndpoint = oldGatewayEndpoint.strip()
                if oldGatewayEndpoint.startswith("https://") == False:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : invalid value provided for old gateway ENDPOINT base. The values MUST start with https://")
                if oldGatewayEndpoint not in gatewaysFromSouceSystem:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : invalid value provided. Thje value({}) given is not present in the source system.".format(oldGatewayEndpoint))
                gatewayEndpointMap[oldGatewayEndpoint] = key1
                gatewayAPIEndpointBaseMap[oldGatewayEndpoint + "^" + gatewaysFromSouceSystem[oldGatewayEndpoint]["api_endpoint_base"]] = val[2]
                
        print()
        print()
        
        #find if any old gateways that are not mapped
        c5 = 0
        listOfNotMappedGateways = ""
        for key in gatewaysFromSouceSystem:
            eachGW = gatewaysFromSouceSystem[key]
            if key not in gatewayEndpointMap:
                c5 = c5 + 1
                listOfNotMappedGateways = listOfNotMappedGateways + str(c5) + ".title : " + eachGW["title"] + "    api_endpoint_base : " + eachGW["api_endpoint_base"] + "    endpoint : "+ eachGW["endpoint"] + "\n"
        
        print()
        print()
        print ("MAPPING BETWEEN OLD GATEWAY MANAGER/DIRECTOR IN SOURCE SYSTEM AND NEW GATEWAY MANAGER/DIRECTOR IN TARGET SYSTEM (gateway info in catalogs will be updated based on this)")
        print ("*************************************************************************************************************************************************************")
        i = 1
        for oldEP in gatewayEndpointMap:
            print(str(i) + ". OLD ENDPOINT : {}          and        NEW ENDPOINT : {}".format(oldEP, gatewayEndpointMap[oldEP]))
            i = i + 1
        print()

        print()
        print()
        print ("MAPPING BETWEEN OLD GATEWAY API ENDPOINT IN SOURCE SYSTEM AND NEW GATEWAY API ENDPOINT IN TARGET SYSTEM (gateway info in catalogs will be updated based on this)")
        print ("***************************************************************************************************************************************************************")
        i = 1
        for oldAPIEPBase in gatewayAPIEndpointBaseMap:
            print(str(i) + ". OLD GW API_ENDPOINT_BASE : {}          and        NEW GW API_ENDPOINT_BASE : {}".format(oldAPIEPBase[oldAPIEPBase.index("^")+1:], gatewayAPIEndpointBaseMap[oldAPIEPBase]))
            i = i + 1
        print()
        print()
        
        
        if c5 > 0:
            print ("LIST OF GATWEWAYS FROM SOURCE SYSTEM(OLD GATEWAYS) THAT NOT MAPPED TO A NEW GATEWAYS IN THE TARGET SYSTEM:")
            print ("**********************************************************************************************************")
            print (listOfNotMappedGateways)
            print ("These gateways if being used in catalogs/space will be left as it is and will be still referring to the old gateways.")
            print()
        
        print()
        #check once again if all the new gateways exist in the target system because some we add from config file data
        for oldEP in gatewayEndpointMap:
            if gatewayEndpointMap[oldEP] not in gatewayServicesInTargetDB:
                newAPIEPBase = None
                for each in gatewayAPIEndpointBaseMap:
                    if each.startswith(oldEP):
                        newAPIEPBase = gatewayAPIEndpointBaseMap[each]
                        break
                print ("Time when error occurred :", time.asctime())
                sys.exit("NEW gateway(ENDPOINT: {} and API_ENDPOINT_BASE: {}) NOT found in the target system. Exiting...".format(gatewayEndpointMap[oldEP], newAPIEPBase))
        
        
        if args.silent == False:
            print()
            confirm = input("Confirm that the above mapping is correct by typing yes : ")
            if confirm != None: confirm = confirm.strip()

            confirm = confirm.lower()
            if (confirm != "yes"):
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : Rerun the script and build the correct mapping. Exiting...")
        
        #create migration user registry and user
        # make owner for all provider orgs
        if args.no_migration_user == False:
            print()
            print("ACTION OUTPUT : Migration user will be created and used for migrating the gateway data. The user will be deleted at the end.")
            print()
            createMigrationUserData()
            changeOwnerForProviderOrgs(True)
            print()
        else:
            if args.silent:
                print("ACTION OUTPUT : Provider org credentials will be read from provider_org_credentials.yaml file to migrate the gateway data.")
            else:
                print("ACTION OUTPUT : User will be prompted to enter credentials for each provider org and used to migrate the gateway data.")

        print()
        # Check every catalog/space and add new gateways corresponding to old gateways.
        print("Start : CHECK EVERY CATALOG/SPACE AND ADD NEW GATEWAYS CORRESPONDING TO THE OLD GATEWAYS :::")
        porgs = runCommand("apic orgs:list --org_type=provider --fields id,name,title --server " + cloudAdminServer, True)
        porgs = yaml.safe_load(porgs)
        
        print("Number of provider organizations  : " + str(porgs["total_results"]))
        for eachPORG in porgs["results"]:
            print()
            pro1 = "Processing provider org : " + eachPORG["title"]
            print (pro1)
            print ("*" * len(pro1))
            print ()
            
            reuseProviderOrgCredentials = None
            if args.silent:
                if providerOrgServer != None:
                    if args.no_migration_user == False:
                        reuseProviderOrgCredentials = "yes"
                    else:
                        if "provider_org_credentials" in porg_credentials and "useSameCredentialsForAllProviderOrgs" in porg_credentials["provider_org_credentials"] and porg_credentials["provider_org_credentials"]["useSameCredentialsForAllProviderOrgs"] == True:
                            reuseProviderOrgCredentials = "yes"
                else:
                    reuseProviderOrgCredentials = "no"
            else:
                if providerOrgServer != None:
                    reuseProviderOrgCredentials = input("Use the same provider org credentials entered previously for this provider org, " + eachPORG["title"] + " (enter yes/no) : ")
                    if reuseProviderOrgCredentials == None:
                        reuseProviderOrgCredentials = "no"
                    else:
                        reuseProviderOrgCredentials = reuseProviderOrgCredentials.lower()
            
            if reuseProviderOrgCredentials != None: reuseProviderOrgCredentials = reuseProviderOrgCredentials.strip()
            if reuseProviderOrgCredentials != "yes":
                porgServer = None
                porgUsername = None
                porgPassword = None
                porgRealm = None
                apiKey = None
                
                isSSOAuth4PORG = None
                
                validRealms = []
                realmsString = ""
                identityProviders = runCommand("apic identity-providers:list --scope provider --fields title,realm --server " + args.server, True)
                identityProviders = yaml.safe_load(identityProviders)["results"]
                for each in identityProviders:
                    realmsString = realmsString + "      For " + each["title"] + " " * (40 - len(each["title"])) + ", realm : " + each["realm"] + "\n"
                    validRealms.append(each["realm"])
                    
                if args.silent:
                    if args.no_migration_user == False:
                        porgServer = args.api_manager_hostname
                        porgUsername = migration_user_name
                        porgPassword = migrationUserPw
                        porgRealm = migrationUserRealm
                    else:
                        thisPORGCreds = None
                        if "provider_org_credentials" in porg_credentials and eachPORG["name"] in porg_credentials["provider_org_credentials"]:
                            thisPORGCreds = porg_credentials["provider_org_credentials"][eachPORG["name"]]
                        else:
                            if porg_credentials["provider_org_credentials"]["useSameCredentialsForAllProviderOrgs"] == True:
                                for eachKey in porg_credentials["provider_org_credentials"]:
                                    if eachKey != "apiManagerHostName" and eachKey != "useSameCredentialsForAllProviderOrgs":
                                        thisPORGCreds = porg_credentials["provider_org_credentials"][eachKey]
                                        break

                        if "apiManagerHostName" in porg_credentials["provider_org_credentials"]:
                            porgServer = porg_credentials["provider_org_credentials"]["apiManagerHostName"]

                        if thisPORGCreds != None:
                            if "username" in thisPORGCreds and "password" in thisPORGCreds:
                                isSSOAuth4PORG = "no"
                                porgUsername = thisPORGCreds["username"]
                                porgPassword = thisPORGCreds["password"]
                                if "realm" in thisPORGCreds:
                                    porgRealm = thisPORGCreds["realm"]
                            else:
                                isSSOAuth4PORG = "yes"
                                if "apiKey" in thisPORGCreds: apiKey = thisPORGCreds["apiKey"]
                else:
                    if args.no_migration_user:
                        porgServer = input("Enter the hostname(from target system) to connect to api manager for this provider org, " + eachPORG["title"] + " : ")
                        isSSOAuth4PORG = input("is SSO authentication type (yes or no) : ")
                        if isSSOAuth4PORG != None: isSSOAuth4PORG = isSSOAuth4PORG.strip()
                        isSSOAuth4PORG = isSSOAuth4PORG.lower()
                
                        if isSSOAuth4PORG != "yes":
                            isSSOAuth4PORG = "no"
                
                        print()
                        if isSSOAuth4PORG == "no":
                            print ("Authentication using username/password:")
                            porgUsername = input("Enter the username for the provider org, " + eachPORG["title"] + " : ")
                            porgPassword = input("Enter the password for the provider org, " + eachPORG["title"] + " : ")
                            print()
                            print ("Valid realms : ")
                            print (realmsString)
                            print()
                            porgRealm = input("Enter realm name the user belongs to : ")
                        else:
                            print ("Authentication using sso:")
                            output = runCommand("apic cloud-settings:info --format yaml --server " + args.server, True)
                            provider_endpoint = yaml.safe_load(output)["provider_endpoint"]
                            print ()
                            print("Please copy and paste the URL in a browser and select the authentication mechanism for SSO/OIDC based authentication.")
                            print ("URL : " + provider_endpoint + "/auth/manager/sign-in/?from=TOOLKIT")
                            print ("Once you get the token, copy it and enter the vaue for api key")
                            print ()
                            apiKey = input("Enter the api key value after authentication using sso : ")
                    else:
                        porgServer = args.api_manager_hostname
                        porgUsername = migration_user_name
                        porgPassword = migrationUserPw
                        porgRealm = migrationUserRealm

                if porgServer != None: porgServer = porgServer.strip()
                if apiKey != None: apiKey = apiKey.strip()
                if porgUsername != None: porgUsername = porgUsername.strip()
                if porgPassword != None: porgPassword = porgPassword.strip()
                if porgRealm != None: porgRealm = porgRealm.strip()

                if (isSSOAuth4PORG == "yes" and (apiKey == None or apiKey == "")) or (isSSOAuth4PORG != "yes" and (porgUsername == None or porgUsername == "" or porgPassword == None or porgPassword == ""  or porgRealm == None or porgRealm == "")):
                    if skipPOrgsWithMissingCredentials == True:
                        print("ACTION OUTPUT : SKIP_PORGS_WITH_MISSING_CREDENTIALS is set to true. Skipping provider org with name, {} as credentials not provided/given. ".format(eachPORG["name"]))
                        continue
                    else:
                        print ("Time when error occurred :", time.asctime())
                        sys.exit("ERROR : provider org credentials for provider org : {} not given. Check the values of apiKey or username/password/realm. Migration will not happpen for this porg. Exiting...".format(eachPORG["name"]))

                removeAPICToolkitTokenFile()
                if isSSOAuth4PORG == "yes":
                    runCommand("apic login --sso --context provider --server " + porgServer + " --apiKey " + apiKey, False, 1)
                else:
                    if porgRealm not in validRealms:
                        print ("Time when error occurred :", time.asctime())
                        sys.exit("ERROR : Not a valid realm for the flag, Input realm value : [{}]. Exiting...".format(porgRealm))
                    runCommand("apic login --server " + porgServer + " --realm " + porgRealm + " --username " + porgUsername + " --password '" + porgPassword + "'", False, 1)
                    
                providerOrgServer = porgServer
            
            
            catalogs = runCommand("apic catalogs:list --org " + eachPORG["name"] + " --fields id,name,title --server " + providerOrgServer, True)
            catalogs = yaml.safe_load(catalogs)

            # export data for validation - start
            if "export_data_for_validation" in managementSubsystemDetails and managementSubsystemDetails["export_data_for_validation"] == True:
                if "export_data_orgs_list" in managementSubsystemDetails and eachPORG["name"] not in managementSubsystemDetails["export_data_orgs_list"]:
                    for eachCatalog in catalogs["results"]:
                        if os.path.exists(DATA_TEMP_DIR + "/" + "catalog-setting.yaml"):
                            os.remove(DATA_TEMP_DIR + "/" + "catalog-setting.yaml")
                        catalogSetting = runCommand("apic catalog-settings:get --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --server " + providerOrgServer + " --output " + DATA_TEMP_DIR, True)
                        catalogSetting = catalogSetting.strip()
                        catalogSettingYamlFileName = catalogSetting[catalogSetting.index("/"):catalogSetting.index(".yaml")] + ".yaml"
                        if os.path.exists(catalogSettingYamlFileName):
                            text_file = open(catalogSettingYamlFileName, "r")
                            config1 = text_file.read()
                            catalogSetting = yaml.safe_load(config1)
                            text_file.close()
                        else:
                            print ("Time when error occurred :", time.asctime())
                            sys.exit("ERROR : catalog-setting.yaml file NOT found, filename : {}. Exiting...".format(catalogSettingYamlFileName))
                        spacesEanbled = catalogSetting["spaces_enabled"]
                        if spacesEanbled:
                            spaces = runCommand("apic spaces:list --fields name --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --server " + providerOrgServer, True)
                            spaces = yaml.safe_load(spaces)
                            for eachSpace in spaces["results"]:
                                print ("\nExport gateway related data for validation, org : " + eachPORG["name"] + " , catalog : " + eachCatalog["name"] + " and space : " + eachSpace["name"])
                                print ("***********************************************************************************************")
                                dir1 = DATA_DIR + "/" + managementSubsystemName + "/resources/orgs/catalogs___" + eachPORG["name"] + "/spaces____" + eachCatalog["name"]
                                for eachResource2 in apic_resources2:
                                    exportResourceData(dir1, eachResource2, apic_resources2[eachResource2], " --org " + eachPORG["name"] + " --catalog " + eachCatalog["name"] + " --space " + eachSpace["name"], eachSpace["name"], providerOrgServer)
                        else:
                            print ("\nExport gateway related data for validation, org : " + eachPORG["name"] + " and catalog : " + eachCatalog["name"])
                            print ("***********************************************************************************************")
                            dir1 = DATA_DIR + "/" + managementSubsystemName + "/resources/orgs/catalogs___" + eachPORG["name"]
                            for eachResource in apic_resources1:
                                exportResourceData(dir1, eachResource, apic_resources1[eachResource], " --org " + eachPORG["name"] + " --catalog " + eachCatalog["name"], eachCatalog["name"], providerOrgServer)
                    config["management_subsystem"][managementSubsystemName]["export_data_orgs_list"].append(eachPORG["name"])
                    with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
                            yaml.dump(config, configFile,  default_flow_style=False)
            # export data for validation - end

            print()
            print("Number of catalogs in the provider org, " + eachPORG["title"] + " : " + str(catalogs["total_results"]))
            for eachCatalog in catalogs["results"]:
                print()
                cat1 = "Processing catalog with title : " + eachCatalog["title"] +" and provider org : " + eachPORG["title"]	
                print (cat1) 
                print("#" * len(cat1))
                
                if os.path.exists(DATA_TEMP_DIR + "/" + "catalog-setting.yaml"):
                    os.remove(DATA_TEMP_DIR + "/" + "catalog-setting.yaml")
                catalogSetting = runCommand("apic catalog-settings:get --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --server " + providerOrgServer + " --output " + DATA_TEMP_DIR, True)
                catalogSetting = catalogSetting.strip()
                catalogSettingYamlFileName = catalogSetting[catalogSetting.index("/"):catalogSetting.index(".yaml")] + ".yaml"
                if os.path.exists(catalogSettingYamlFileName):
                    text_file = open(catalogSettingYamlFileName, "r")
                    config1 = text_file.read()
                    catalogSetting = yaml.safe_load(config1)
                    text_file.close()
                else:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : catalog-setting.yaml file NOT found, filename : {}. Exiting...".format(catalogSettingYamlFileName))
                
                spacesEanbled = catalogSetting["spaces_enabled"]
                legacyEndpointBehaviour = None
                if "legacy_endpoint_behavior" in catalogSetting:
                    legacyEndpointBehaviour = catalogSetting["legacy_endpoint_behavior"]
                
                print ("\nAre spaces enabled in the catalog : ", spacesEanbled)
                print ("Legacy endpoint behaviour in catalog setting : ", legacyEndpointBehaviour)
                print()
                
                if spacesEanbled:
                    spaces = runCommand("apic spaces:list --fields id,name,title --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --server " + providerOrgServer, True)
                    spaces = yaml.safe_load(spaces)
                    
                    print("Number of spaces in the catalog : " + str(spaces["total_results"]))
                    for eachSpace in spaces["results"]:
                        print()
                        space1 = "Processing space with title : " + eachSpace["title"] + ", catalog : " + eachCatalog["title"] + " and provider org : " + eachPORG["title"]
                        print(space1)
                        print("-" * len(space1))
                        print()
                        
                        configuredGWListForSpace = runCommand("apic configured-gateway-services:list --fields id,name,title,catalog_base,endpoint,api_endpoint_base,url --scope space --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --space "+ eachSpace["name"] + " --server " + providerOrgServer, True)
                        configuredGWListForSpace = yaml.safe_load(configuredGWListForSpace)
                        c1 = configuredGWListForSpace["total_results"]
                        if c1 > 0:
                            old2newConfGWURLMAP = {}
                            configuredGWMap = {}
                            for eachConfiguredGW in configuredGWListForSpace["results"]:
                                configuredGWMap[eachConfiguredGW["endpoint"]] = eachConfiguredGW
                            
                            for ep in configuredGWMap:
                                if ep in gatewayEndpointMap: # old configured gw
                                    oldConfGW = configuredGWMap[ep]
                                    print()
                                    print ("Processing for old configured gateway :: " + oldConfGW["title"])
                                    newEndpoint = gatewayEndpointMap[ep]
                                    newConfGWId = None
                                    if newEndpoint in configuredGWMap: #new configured gateway already exists
                                        newConfGW = configuredGWMap[newEndpoint]
                                        newConfGWName = newConfGW["name"]
                                        old2newConfGWURLMAP[oldConfGW["url"]] =  newConfGW["url"]
                                        print ("ACTION OUTPUT : New configured gateway(title :{} and url : {}) ALREADY EXISTS that corrosponds to older configured gateway(title :{} and url : {})".format(newConfGW["title"], newConfGW["catalog_base"], oldConfGW["title"], oldConfGW["catalog_base"]))
                                        print()
                                    else:
                                        #create new configured gw
                                        gwId = gatewayServicesInTargetDB[newEndpoint]
                                        configuredGatewayServiceCreateInput = {
                                            "gateway_service_url" : "https://" + providerOrgServer + "/api/orgs/" + eachPORG["id"] + "/gateway-services/" + gwId[0:gwId.index("|")]
                                        }
                                        print ("Input body for create configured gateway service : ", configuredGatewayServiceCreateInput)
                                        f3 = DATA_TEMP_DIR + "/" + "configuredGatewayServiceCreateInput.yaml"
                                        with open(f3, 'w') as configuredGatewayServiceCreateFile:
                                            yaml.dump(configuredGatewayServiceCreateInput, configuredGatewayServiceCreateFile,  default_flow_style=False)
                                        c1 = runCommand("apic configured-gateway-services:create --scope space --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --space "+ eachSpace["name"] + " --server " + providerOrgServer + " " + f3, False)
                                        c1 = c1.strip()
                                        newConfGWName = c1[c1.rindex("/")+1:] #id
                                        old2newConfGWURLMAP[oldConfGW["url"]] =  c1[c1.index("https://"):]
                                        print ("ACTION OUTPUT :  New configured gateway added to space : " + c1)
                                        print()
                                    migrateExtensions("space", eachPORG["name"], eachCatalog["name"], eachSpace["name"], oldConfGW["name"], newConfGWName)
                                    print()
                                    migrateCustomPolicies("space", eachPORG["name"], eachCatalog["name"], eachSpace["name"], oldConfGW["name"], newConfGWName)
                                    print()
                                    migrateGlobalPolicies("space", eachPORG["name"], eachCatalog["name"], eachSpace["name"], oldConfGW["name"], newConfGWName)    
                                    print()
                                else:
                                    if ep not in gatewayEndpointMap.values():
                                        print ("ACTION OUTPUT : No mapping for this gateway enpoint : {}. Leaving the gateway as it is in the catalog : {} and org : {}".format(ep, eachCatalog["title"], eachPORG["title"]))
                                    else:
                                        print ("ACTION OUTPUT : This is a new configured gateway with name : {}.".format(configuredGWMap[ep]["name"]))
                                    print()
                            
                            if legacyEndpointBehaviour == "enabled":
                                updateLegacyVanityEndpointsInCatalog(catalogSetting, eachPORG["name"], eachCatalog["name"], old2newConfGWURLMAP)
                            updateGetwayInfoInProducts("space", eachPORG["name"], eachCatalog["name"], eachSpace["name"], old2newConfGWURLMAP)
                            
                            #deleting old configured gateways which got replaced by new ones(delete by name)
                            for each in old2newConfGWURLMAP:
                                confGWId = each[each.rindex("/")+1:]
                                a3 = runCommand("apic configured-gateway-services:delete --scope space --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --space "+ eachSpace["name"] + " --server " + providerOrgServer + " " + confGWId, False, 2, False) 
                                if "EOF" in a3:
                                    print ("WARNING : Try again from API manager UI. Failed to delete old configured gateway service from space : {}, catalog : {}, org : {} with name/url : {}".format(eachSpace["name"], eachCatalog["name"] , eachPORG["name"], a3))
                                elif "Not found" in a3:
                                    print ("May be already deleted. Could not find old configured gateway service from space : {}, catalog : {}, org : {} with name/url : {}".format(eachSpace["name"], eachCatalog["name"] , eachPORG["name"], a3))
                                elif "Error" in a3 or "error" in a3:
                                    sys.exit("ERROR : Could not delete old configured gateway service from space : {}, catalog : {}, org : {} with name/url : {}".format(eachSpace["name"], eachCatalog["name"] , eachPORG["name"], a3))
                                else:
                                    print ("Deleted old configured gateway service from space : {}, catalog : {}, org : {} with name/url : {}".format(eachSpace["name"], eachCatalog["name"] , eachPORG["name"], a3))
                            print()
                        else:
                            print("ACTION OUTPUT : Gateways are NOT configured for the org : {}, catalog : {} and space : {}".format(eachPORG["title"], eachCatalog["title"], eachSpace["title"]))
                            print()
                else:
                    #catalog
                    configuredGWList = runCommand("apic configured-gateway-services:list --fields id,name,title,catalog_base,endpoint,api_endpoint_base,url --scope catalog --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --server " + providerOrgServer, True) 
                    configuredGWList = yaml.safe_load(configuredGWList)
                    c1 = configuredGWList["total_results"]
                    if c1 > 0:
                        old2newConfGWURLMAP = {}
                        configuredGWMap = {}
                        for eachConfiguredGW in configuredGWList["results"]:
                            configuredGWMap[eachConfiguredGW["endpoint"]] = eachConfiguredGW
                        
                        for ep in configuredGWMap:
                            if ep in gatewayEndpointMap: # old configured gw
                                oldConfGW = configuredGWMap[ep]
                                print()
                                print ("Processing for old configured gateway :: " + oldConfGW["title"])
                                newEndpoint = gatewayEndpointMap[ep]
                                newConfGWId = None
                                if newEndpoint in configuredGWMap: #new configured gateway already exists
                                    newConfGW = configuredGWMap[newEndpoint]
                                    newConfGWName = newConfGW["name"]
                                    old2newConfGWURLMAP[oldConfGW["url"]] =  newConfGW["url"]
                                    print ("ACTION OUTPUT : New configured gateway(title :{} and url : {}) ALREADY EXISTS that corrosponds to older configured gateway(title :{} and url : {})".format(newConfGW["title"], newConfGW["catalog_base"], oldConfGW["title"], oldConfGW["catalog_base"]))
                                    print()
                                else:
                                    #create new configured gw
                                    gwId = gatewayServicesInTargetDB[newEndpoint]
                                    configuredGatewayServiceCreateInput = {
                                        "gateway_service_url" : "https://" + providerOrgServer + "/api/orgs/" + eachPORG["id"] + "/gateway-services/" + gwId[0:gwId.index("|")]
                                    }
                                    print ("Input body for create configured gateway service : ", configuredGatewayServiceCreateInput)
                                    f3 = DATA_TEMP_DIR + "/" + "configuredGatewayServiceCreateInput.yaml"
                                    with open(f3, 'w') as configuredGatewayServiceCreateFile:
                                        yaml.dump(configuredGatewayServiceCreateInput, configuredGatewayServiceCreateFile,  default_flow_style=False)
                                    cg1 = runCommand("apic configured-gateway-services:create --scope catalog --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --server " + providerOrgServer + " " + f3, True) 
                                    cg1 = cg1.strip()
                                    newConfGWName = cg1[cg1.rindex("/")+1:] #id
                                    old2newConfGWURLMAP[oldConfGW["url"]] =  cg1[cg1.index("https://"):]
                                    print ("ACTION OUTPUT :  New configured gateway added to catalog : " + cg1)
                                    print()
                                migrateExtensions("catalog", eachPORG["name"], eachCatalog["name"], None, oldConfGW["name"], newConfGWName)
                                print()
                                migrateCustomPolicies("catalog", eachPORG["name"], eachCatalog["name"], None, oldConfGW["name"], newConfGWName)
                                print()
                                #global polices and global_policy_prehook/posthook/error
                                migrateGlobalPolicies("catalog", eachPORG["name"], eachCatalog["name"], None, oldConfGW["name"], newConfGWName)  
                                print()
                            else:
                                if ep not in gatewayAPIEndpointBaseMap.values():
                                    print ("ACTION OUTPUT : No mapping for this gateway enpoint : {}. Leaving the gateway as it is in the catalog : {} and org : {}".format(ep, eachCatalog["title"], eachPORG["title"]))
                                else:
                                    print ("ACTION OUTPUT : This is a new configured gateway with name : {}.".format(configuredGWMap[ep]["name"]))
                                print()
                        
                        if legacyEndpointBehaviour == "enabled":
                            updateLegacyVanityEndpointsInCatalog(catalogSetting, eachPORG["name"], eachCatalog["name"], old2newConfGWURLMAP)
                        updateGetwayInfoInProducts("catalog", eachPORG["name"], eachCatalog["name"], None, old2newConfGWURLMAP)
                        
                        #deleting old configured gateways which got replaced by new ones(delete by name)
                        for each in old2newConfGWURLMAP:
                            confGWId = each[each.rindex("/")+1:]
                            a3 = runCommand("apic configured-gateway-services:delete --scope catalog --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --server " + providerOrgServer + " " + confGWId, False, 2, False)
                            if "EOF" in a3:
                                print ("WARNING : Try again from API manager UI. Failed to delete old configured gateway service from catalog : {}, org : {} with name/url : {}".format(eachCatalog["name"] , eachPORG["name"], a3))
                            elif "Not found" in a3:
                                print ("May be already deleted. Could not find old configured gateway service from catalog : {}, org : {} with name/url : {}".format(eachCatalog["name"] , eachPORG["name"], a3))
                            elif "Error" in a3 or "error" in a3:
                                sys.exit("ERROR : Could not delete old configured gateway service from catalog : {}, org : {} with name/url : {}".format(eachCatalog["name"] , eachPORG["name"], a3))
                            else:
                                print ("Deleted old configured gateway service from catalog : {}, org : {} with name/url : {}".format(eachCatalog["name"] , eachPORG["name"], a3))
                        print()
                    else:
                        print("ACTION OUTPUT : Gateways are NOT configured for the org : {} and catalog : {}".format(eachPORG["title"], eachCatalog["title"]))
                        print()

        removeAPICToolkitTokenFile()
        loginToCloudManager()
        # make original owner  as the owner for all provider orgs
        #delete migration user registry and user
        if args.no_migration_user == False:
            print()
            changeOwnerForProviderOrgs(False)
            deleteMigrationUserData()

        print()
        print()
        print("Update default gateways in cloud setting::")
        print("******************************************")
        #update gateways in cloud settings
        if os.path.exists(DATA_TEMP_DIR + "/" + "CloudSetting.yaml"):
            os.remove(DATA_TEMP_DIR + "/" + "CloudSetting.yaml")
        cloudSetting = runCommand("apic cloud-settings:get --fields gateway_service_default_urls --server " + cloudAdminServer + " --output " + DATA_TEMP_DIR, True)
        cloudSetting = cloudSetting.strip()
        cloudSettingYamlFileName = cloudSetting.split()[1]
        if os.path.exists(cloudSettingYamlFileName):
            text_file = open(cloudSettingYamlFileName, "r")
            config1 = text_file.read()
            cloudSetting = yaml.safe_load(config1)
            text_file.close()
        else:
            print ("Time when error occurred :", time.asctime())
            sys.exit("ERROR : CloudSetting.yaml file NOT found. Exiting...")
            
        if "gateway_service_default_urls" in cloudSetting:
            defaultGW_urls = cloudSetting["gateway_service_default_urls"]
            if defaultGW_urls != None and len(defaultGW_urls) > 0:
                #create a map of url and api_endpoint base
                url2endpoint = {}
                for ep in gatewayServicesInTargetDB:
                    url = gatewayServicesInTargetDB[ep][gatewayServicesInTargetDB[ep].rindex("|")+1:]
                    url2endpoint[url] = ep
                
                needUpdate = False
                for index in range(len(defaultGW_urls)):
                    ep = url2endpoint[defaultGW_urls[index]]
                    if ep in gatewayEndpointMap:
                        needUpdate = True
                        newEP = gatewayEndpointMap[ep]
                        defaultGW_urls[index] = gatewayServicesInTargetDB[newEP][gatewayServicesInTargetDB[newEP].rindex("|")+1:]
                
                if needUpdate:
                    updateCloudSettingRequest = {
                      "gateway_service_default_urls": defaultGW_urls
                    }
                    print ("Updating cloud settings default gateways with new gateways : ", updateCloudSettingRequest)
                    fname = DATA_TEMP_DIR + "/" + "updateCloudSettingGateways.yaml"
                    with open(fname, 'w') as updateCloudSettingGatewaysFile:
                        yaml.dump(updateCloudSettingRequest, updateCloudSettingGatewaysFile,  default_flow_style=False)
                    runCommand("apic cloud-settings:update --server " + cloudAdminServer + " " + fname, True)
                    print ("ACTION OUTPUT : Updated defaulted gateways in cloud settings.")
                    print()
                else:
                    print ("ACTION OUTPUT : The default gateways in cloud setting are already updated or no update needed.")
                    
            else:
                print ("ACTION OUTPUT : No default gateways set in cloud settings. No changes needed to cloud settings.")
            
            
        # delete the old gateways services
        print()
        print()
        print ("Delete source system gateways::::")
        print ("*********************************")
        m = 1
        foundOldGateways = False
        for key in gatewayServicesInTargetDB:
            da1 = gatewayServicesInTargetDB[key].split("|")
            if key in gatewaysFromSouceSystem:
                foundOldGateways = True
                print (str(m) + ". The gateway (title : {}, api endpoint : {}) from source system::".format(da1[1], da1[2]))
                m = m + 1
                if key not in gatewayEndpointMap:
                    print ("   The gateway (title : {}, api endpoint : {}) from source system is NOT mapped to any new gateway in the target system".format(da1[1], da1[2]))
                    print ("   It's assumed that the old gateway will be still used from the target APIC system or the gateway is migrated later.")
                    print ("   Not deleting the gateway. If the gateway has to be deleted, it has to be manually removed from the catalogs/spaces where its used and then deleted from cloud manager/topology.")
                    print()
                    continue
                    
                id1 = da1[0]
                azoneid = gatewaysFromSouceSystem[key]["availability_zone_url"].strip()
                azoneid = azoneid[azoneid.rindex("/") + 1:]
                services = runCommand("apic gateway-services:delete --server " + cloudAdminServer + " --org admin --availability-zone " + azoneid + " " + id1, True)
                print ("ACTION OUTPUT :Deleted the old gateway service which is from the source system, title : {}, api endpoint : {}, endpoint : {}  ".format(da1[1], da1[2], key))
                print()
        if foundOldGateways == False:
            print ("All old gateways are already deleted.")
        print ()
        
        #unassociate old analytics with old gateways, delete old analytics. create new analytics
        if "registered_analytics" in managementSubsystemDetails and len(managementSubsystemDetails["registered_analytics"]) > 0:
            analyticsFromSouceSystem = managementSubsystemDetails["registered_analytics"]
            
            aServiceMap = getAnalyticsServices()
            gServiceMap = getGatewayServices(True)
            unassociateAnalyticsFromGWPayload = {
                "analytics_service_url": None
            }
            gwUpdateFilename = DATA_TEMP_DIR + "/unassociateAnalyticsFromGWPayload.yaml"
            with open(gwUpdateFilename, 'w') as f6:
                yaml.dump(unassociateAnalyticsFromGWPayload, f6, default_flow_style=False)

            for eachAnalyticsIngestionHost in analyticsFromSouceSystem:
                eachAnalytics = analyticsFromSouceSystem[eachAnalyticsIngestionHost]
                ingestionEndpointTLSClientProfileURL = eachAnalytics["ingestion_endpoint_tls_client_profile_url"]
                # get get correct url for ingestion_endpoint_tls_client_profile_url
                tlsClientProfiles = runCommand("apic tls-client-profiles:list-all -o admin --fields id,name,url --server " + cloudAdminServer, True)
                tlsClientProfiles = yaml.safe_load(tlsClientProfiles)
                for eachTLSClientProfile in tlsClientProfiles["results"]:
                    if ingestionEndpointTLSClientProfileURL.endswith(eachTLSClientProfile["id"]):
                        ingestionEndpointTLSClientProfileURL = eachTLSClientProfile["url"]
                        break

                if eachAnalyticsIngestionHost in aServiceMap: # source analytics record still existing in db
                    azonename = aServiceMap[eachAnalyticsIngestionHost]
                    azonename = azonename[azonename.index("^")+1:]
                    print ("Processing analytics service with name : {} and id : {}".format(eachAnalytics["name"], eachAnalytics["id"]))
                    if eachAnalytics["id"] in gServiceMap.values():
                        #unassociate from all the gateways
                        for eachGWName in gServiceMap:
                            if gServiceMap[eachGWName] == eachAnalytics["id"]:
                                runCommand("apic gateway-services:update --org admin --server " + cloudAdminServer + " --availability-zone " + azonename + " " + eachGWName + " " + gwUpdateFilename)
                                print ("ACTION OUTPUT : The analytics service with title : {} is unassociated with OLD gateway service with name : {}.".format(eachAnalytics["title"], eachGWName))
                                print()

                    print()
                    #add new analytics service if it exists in the mapping that corrosponding to this old one
                    if gateway_portal_mapping != None and "analytics_mapping" in gateway_portal_mapping and eachAnalytics["name"] in gateway_portal_mapping["analytics_mapping"]:
                        ingesEndpointMap = gateway_portal_mapping["analytics_mapping"][eachAnalytics["name"]]
                        if eachAnalyticsIngestionHost in ingesEndpointMap:
                            newAIEndpoint = ingesEndpointMap[eachAnalyticsIngestionHost]
                            if newAIEndpoint != None:
                                newAIEndpoint = newAIEndpoint.strip()   
                                if newAIEndpoint != "" and newAIEndpoint != "https://NEW_ANALYTICS_INGESTION_ENDPOINT_HOST_IN_TARGET_SYSTEM":
                                    if newAIEndpoint.startswith("https://") == False:
                                        newAIEndpoint = "https://" + newAIEndpoint

                                    # check using endpoint because configurator job can insert analytics service with a specific name even though it exists
                                    if newAIEndpoint not in aServiceMap:#checking if new service already created check
                                        apayload = {
                                            "name": eachAnalytics["name"]+"new",
                                            "title": eachAnalytics["name"]+"new",
                                            "endpoint": newAIEndpoint,
                                            "client_endpoint_tls_client_profile_url": ingestionEndpointTLSClientProfileURL
                                        }
                                        
                                        sourceCommunicationKind = None
                                        targetCommunicationKind = None
                                        if "communication_kind" in eachAnalytics:
                                            sourceCommunicationKind = eachAnalytics["communication_kind"]
                                        if sourceCommunicationKind != None and sourceCommunicationKind in ingesEndpointMap:
                                            targetCommunicationKind = ingesEndpointMap[sourceCommunicationKind]
                                        if targetCommunicationKind != None and targetCommunicationKind != "external" and targetCommunicationKind != "internal_svc":
                                            sys.exit("Invalid communication kind({}) provided while registering analytics. Exiting...".format(targetCommunicationKind))
                                        if targetCommunicationKind == "internal_svc":
                                            apayload["internal_svc_endpoint"] = newAIEndpoint
                                            apayload["communication_from_apim_kind"] = "internal_svc"
                                            apayload["internal_svc_endpoint_tls_client_profile_url"] = ingestionEndpointTLSClientProfileURL

                                        newAnalyFileName = DATA_TEMP_DIR + "/" + apayload["name"] + ".yaml"
                                        with open(newAnalyFileName, 'w') as f5:
                                            yaml.dump(apayload, f5,  default_flow_style=False)
                                        aOut = runCommand("apic analytics-services:create --org admin --server " + cloudAdminServer + " --availability-zone " + azonename + " " + newAnalyFileName, True, 1, False)
                                        print ("ACTION OUTPUT : Created new analytics with title : {} in the target system.".format(apayload["title"]))
                                        aOutURL = aOut[aOut.index(" "):].strip()

                                        #associate the new analytics service to gateways
                                        #todo
                                    else:
                                        aname = aServiceMap[newAIEndpoint]
                                        aname = aname[0:aname.index("^")]
                                        print ("ACTION OUTPUT : New analytics with name, {} already created in the target system.".format(aname))

                                    print()
                                    #delete the old analytics service
                                    runCommand("apic analytics-services:delete --org admin --server " + cloudAdminServer + " --availability-zone " + azonename + " " + eachAnalytics["name"] , True, 0, False)
                                    print ("ACTION OUTPUT : Deleted old analytics service, {} from cloud manager".format(eachAnalytics["name"]))
                                    print()
                                else:
                                    print ("ACTION OUTPUT : Old analytics with name : {} not migrated yet.".format(eachAnalytics["name"]))
                            else:
                                print ("ACTION OUTPUT : Old analytics with name : {} NOT migrated yet.".format(eachAnalytics["name"]))
                else:
                    print ("ACTION OUTPUT : The analytics service with name : {} is already deleted.".format(eachAnalytics["name"]))
        print()
        print()


def updateLegacyVanityEndpointsInCatalog(catalogSetting, orgName, catalogName, old2newConfGWURLMAP):
    if "v5_endpoint_substitution_behavior" in catalogSetting and "base_endpoints" in catalogSetting["v5_endpoint_substitution_behavior"]:
        base_endpoints = catalogSetting["v5_endpoint_substitution_behavior"]["base_endpoints"]
        dataUpdated = False
        for eachBaseEndpoint in base_endpoints:
            if eachBaseEndpoint["gateway_service_url"] in old2newConfGWURLMAP:
                eachBaseEndpoint["gateway_service_url"] = old2newConfGWURLMAP[eachBaseEndpoint["gateway_service_url"]]
                dataUpdated = True
         
        if dataUpdated == True:
            updateLegacyVanityEndpointsRequest["v5_endpoint_substitution_behavior"]["base_endpoints"] = base_endpoints
            print ("Updating legacy vanity endpoints, updating catalog setting with request : ", updateLegacyVanityEndpointsRequest)
            f6 = DATA_TEMP_DIR + "/" + "updateLegacyVanityEndpointsRequest.yaml"
            with open(f6, 'w') as updateLegacyVanityEndpointsFile:
                yaml.dump(updateLegacyVanityEndpointsRequest, updateLegacyVanityEndpointsFile,  default_flow_style=False)
            runCommand("apic catalog-settings:update --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " " + f6, False)
            print ("ACTION OUTPUT : Updated legacy vanity endpoints in catalog : {} and provider org : {}".format(catalogName, orgName))
        else:
            print ("ACTION OUTPUT : Vanity endpoints are already updated or there are no vanity endpoints referring to the old configued gateway.")
    print()

def updateGetwayInfoInProducts(scope, orgName, catalogName, spaceName, old2newConfGWURLMAP):
    if spaceName == None:
        print ("Updating gateway info in products for catalog : {}, org : {}".format(catalogName, orgName))
        products = runCommand("apic products:list-all --format yaml --fields id,name,version,gateway_service_urls --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer, True)
    else:
        print ("Updating gateway info in products for space : {}, catalog : {}, org : {}".format(spaceName, catalogName, orgName))
        products = runCommand("apic products:list-all --format yaml --fields id,name,version,gateway_service_urls --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --space "+ spaceName + " --server " + providerOrgServer, True)
    products = yaml.safe_load(products)
    
    print()
    if products["total_results"] > 0:
        print("Total products  : " + str(products["total_results"]))
        for eachProduct in products["results"]:
            gateway_service_urlsInProduct = eachProduct["gateway_service_urls"]
            print("Checking product with name : " + eachProduct["name"] + " and version :  " + eachProduct["version"] + " and gateways :: ", gateway_service_urlsInProduct)
            
            print()
            gwUpdated = False
            for index in range(len(gateway_service_urlsInProduct)):
                if gateway_service_urlsInProduct[index] in old2newConfGWURLMAP:
                    gwUpdated = True
                    gateway_service_urlsInProduct[index] = old2newConfGWURLMAP[gateway_service_urlsInProduct[index]]
            
            if gwUpdated:
                inputBody = {
                    "gateway_service_urls": gateway_service_urlsInProduct
                }
                #print ("Input body to update gateways in product : ", inputBody)
                fileName = DATA_TEMP_DIR + "/" + "updateProductFile_" + str(random.randint(0, 9999999)) + ".yaml"
                with open(fileName, 'w') as updateProdFile:
                    yaml.dump(inputBody, updateProdFile, default_flow_style=False)
            
                nameVersion = eachProduct["name"] + ":" + eachProduct["version"]
                if spaceName == None:
                    runCommand("apic products:update --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " " + nameVersion + " " + fileName, True)
                else:
                    runCommand("apic products:update --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --space "+ spaceName + " --server " + providerOrgServer + " " + nameVersion + " " + fileName, True) 
                print ("ACTION OUTPUT : Updated gateways in product(name : " + eachProduct["name"] + " and version : " + eachProduct["version"] + "). Updated gateway list :: ", gateway_service_urlsInProduct)
            else:
                print("ACTION OUTPUT : No gateways got changed (already updated to new gateway or still use the old gateway) for product with name : {} and version : {}".format(eachProduct["name"], eachProduct["version"]))
            print()
    else:
        print ("ACTION OUTPUT : No products present in space : {}, catalog : {}, org : {}".format(spaceName, catalogName, orgName))
    print()


def getGlobalPolicyHooks(scope, orgName, catalogName, spaceName, ConfGWName):
    hooks = ["prehook", "posthook", "error"]
    
    if os.path.exists(DATA_TEMP_DIR + "/GlobalPolicyError.yaml"):
        os.remove(DATA_TEMP_DIR + "/GlobalPolicyError.yaml")
    if os.path.exists(DATA_TEMP_DIR + "/GlobalPolicyPrehook.yaml"):
        os.remove(DATA_TEMP_DIR + "/GlobalPolicyPrehook.yaml")
    if os.path.exists(DATA_TEMP_DIR + "/GlobalPolicyPosthook.yaml"):
        os.remove(DATA_TEMP_DIR + "/GlobalPolicyPosthook.yaml")
        
    #if no data, it returns error msg
    if spaceName == None:
       	hooks[0] = runCommand("apic global-policy-prehooks:get --fields global_policy_url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + ConfGWName + " --output " + DATA_TEMP_DIR, False, 1, False)
        hooks[1] = runCommand("apic global-policy-posthooks:get --fields global_policy_url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + ConfGWName + " --output " + DATA_TEMP_DIR, False, 1, False)
        hooks[2] = runCommand("apic global-policy-errors:get --fields global_policy_url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + ConfGWName + " --output " + DATA_TEMP_DIR, False, 1, False)
    else:
        hooks[0] = runCommand("apic global-policy-prehooks:get --fields global_policy_url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + ConfGWName + " --space " + spaceName + " --output " + DATA_TEMP_DIR, False, 1, False)
        hooks[1] = runCommand("apic global-policy-posthooks:get --fields global_policy_url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + ConfGWName + " --space " + spaceName + " --output " + DATA_TEMP_DIR, False, 1, False)
        hooks[2] = runCommand("apic global-policy-errors:get --fields global_policy_url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + ConfGWName + " --space " + spaceName + " --output " + DATA_TEMP_DIR, False, 1, False)
    return hooks    


def migrateGlobalPolicies(scope, orgName, catalogName, spaceName, oldConfGWName, newConfGWName):
    oldGlobalPolicies = None
    if spaceName == None:
        print ("Global policies from OLD configured gateway : {}, catalog: {} and org, {} ::: ".format(oldConfGWName, catalogName, orgName))
        oldGlobalPolicies = runCommand("apic global-policies:list-all --format yaml --fields name,version,global_policy,url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + oldConfGWName, True)
    else:
        print ("Global policies from OLD configured gateway : {}, space : {}, catalog : {} and org : {} ::: ".format(oldConfGWName, spaceName, catalogName, orgName))
        oldGlobalPolicies = runCommand("apic global-policies:list-all --format yaml --fields name,version,global_policy,url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + oldConfGWName + " --space " + spaceName, True)
    oldGlobalPolicies = yaml.safe_load(oldGlobalPolicies)
    
    if oldGlobalPolicies["total_results"] > 0:
        print("Number of global policies in the old configured gateway : " + str(oldGlobalPolicies["total_results"]))
        print()
        newGlobalPolicies = None
        if spaceName == None:
            print ("Global policies from NEW configured gateway : {}, catalog : {} and org : {} ::: ".format(newConfGWName, catalogName, orgName))
            newGlobalPolicies = runCommand("apic global-policies:list-all --format yaml --fields name,version,url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName, False)
        else:
            print ("Global policies from NEW configured gateway : {}, space :{}, catalog : {} and org, {} ::: ".format(newConfGWName, spaceName, catalogName, orgName))
            newGlobalPolicies = runCommand("apic global-policies:list-all --format yaml --fields name,version,url --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " --space " + spaceName, False)
        newGlobalPolicies = yaml.safe_load(newGlobalPolicies)
        
        newGloabalPolicyMap = {}
        if newGlobalPolicies["total_results"] > 0:
            for eachGP in newGlobalPolicies["results"]:
                newGloabalPolicyMap[eachGP["name"] + ":" + eachGP["version"]] = eachGP["url"]
        
        #get prehook, posthook and error data for old configured gateway
        hooksForOldConfiguredGateway = getGlobalPolicyHooks(scope, orgName, catalogName, spaceName, oldConfGWName)
        print ("prehook/posthook/error hook for old configured gateway : ", hooksForOldConfiguredGateway)
        globalPolicyURL4_hooks = [None, None, None]
        i = 0
        for eachHook in hooksForOldConfiguredGateway:
            if not eachHook.startswith("Error"):
                eachHook = eachHook.strip()
                filename = eachHook[eachHook.index("/"):]
                if os.path.exists(filename):
                    text_file = open(filename, "r")
                    d = text_file.read()
                    d = yaml.safe_load(d)
                    globalPolicyURL4_hooks[i] = d["global_policy_url"]
                    text_file.close()
                else:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Could not read one of the prehook/posthook/error file. value of i : {} , filename : {} , eachHookOutput : {} Exiting...".format(i, filename, eachHook))
            i = i + 1        
        print ("global_policy_url for the prehook/posthook/error hook if they exist for the old configured gateway : ", globalPolicyURL4_hooks)
        
        for eachOldGlobalPolicy in oldGlobalPolicies["results"]:
            globalPolicyURL = None
            if eachOldGlobalPolicy["name"] + ":" + eachOldGlobalPolicy["version"] in newGloabalPolicyMap:
                globalPolicyURL = newGloabalPolicyMap[eachOldGlobalPolicy["name"] + ":" + eachOldGlobalPolicy["version"]]
                print ("ACTION OUTPUT : Global policy({}) ALREADY EXISTS in configured gateway : {}, catalog : {} and org : {} ::: ".format(eachOldGlobalPolicy["name"] + ":" + eachOldGlobalPolicy["version"], newConfGWName, catalogName, orgName))
                print()
            else:
                #create new global policy
                filePath = DATA_TEMP_DIR + "/globalpolicy" + eachOldGlobalPolicy["name"] + "_" + eachOldGlobalPolicy["version"] + "_" + str(random.randint(0, 9999999)) + ".yaml"
                with open(filePath , 'w') as gpFile:
                    yaml.dump(eachOldGlobalPolicy["global_policy"], gpFile,  default_flow_style=False)
                    
                if spaceName == None:
                    n1 = runCommand("apic global-policies:create --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " " + filePath, True)
                    print ("ACTION OUTPUT : Created global policy in configured gateway : {}, catalog : {} and org : {} ::: {} ".format(newConfGWName, catalogName, orgName, n1))
                else:
                    n1 = runCommand("apic global-policies:create --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --space " + spaceName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " " + filePath, True)
                    print ("ACTION OUTPUT : Created global policy in configured gateway : {}, space : {}, catalog : {} and org : {} ::: {} ".format(newConfGWName, spaceName, catalogName, orgName, n1))
                print()
                globalPolicyURL = n1[n1.index("https"):]
                globalPolicyURL = globalPolicyURL.strip()
            
            #global_policy_prehook,global_policy_posthook,global_policy_error
            n = 0
            for eachGP_URL4hook in globalPolicyURL4_hooks:
                if eachGP_URL4hook != None and eachGP_URL4hook == eachOldGlobalPolicy["url"]:
                    print("Found one of prehook/posthook/error for global_policy url : {} in old configured gateway : {}".format(eachGP_URL4hook, oldConfGWName))
                    hooksForNEWConfiguredGateway = getGlobalPolicyHooks(scope, orgName, catalogName, spaceName, newConfGWName)
                    if hooksForNEWConfiguredGateway[n].startswith("Error"):
                        content = {
                            "global_policy_url": globalPolicyURL
                        }
                        f4 = DATA_TEMP_DIR + "/" + "global_policy_hook.yaml"
                        with open(f4, 'w') as global_policy_hook:
                            yaml.dump(content, global_policy_hook,  default_flow_style=False)
                        flags = None
                        if spaceName == None:
                           flags = " --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName
                        else:
                           flags = " --scope " + scope + " --org " + orgName + " --catalog "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " --space " + spaceName    
                        res1 = None
                        if n == 0:
                            res1 = runCommand("apic global-policy-prehooks:create" + flags + " " + f4, True)
                        elif n == 1:
                            res1 = runCommand("apic global-policy-posthooks:create" + flags + " " + f4, True)
                        elif n == 2:
                            res1 = runCommand("apic global-policy-errors:create" + flags + " " + f4, True)
                        print("Created one of prehook/posthook/error in new configured gateway : {}, value of n : {} and response : {}".format(newConfGWName, n, res1))
                    else:
                        print("One of prehook/posthook/error {} already created in new configured gateway : {}, value of n : {}".format(hooksForNEWConfiguredGateway[n], newConfGWName, n))
                    print()
                n = n + 1
                    
            
              
        print() 
    else:
        print ("ACTION OUTPUT : No global policies found in the old configured gateway : {}".format(oldConfGWName)) 

    
def migrateCustomPolicies(scope, orgName, catalogName, spaceName, oldConfGWName, newConfGWName):
    oldPolicies = None
    if spaceName == None:
        print ("Custom policies from OLD configured gateway : {}, catalog : {} and org : {} ::: ".format(oldConfGWName, catalogName, orgName))
        oldPolicies = runCommand("apic policies:list-all --format yaml --fields name,version,custom --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + oldConfGWName, True)
    else:
        print ("Custom policies from OLD configured gateway : {}, space : {}, catalog : {} and org : {} ::: ".format(oldConfGWName, spaceName, catalogName, orgName))
        oldPolicies = runCommand("apic policies:list-all --format yaml --fields name,version,custom --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + oldConfGWName + " --space " + spaceName, True)
    oldPolicies = yaml.safe_load(oldPolicies)
    print()
	
    oldPoliciesCustom = {
	    "total_results" : 0,
        "results" : []
    }
	
    for eachPolicy in oldPolicies["results"]:
	    if eachPolicy["custom"] == True:
	        oldPoliciesCustom["total_results"] = oldPoliciesCustom["total_results"] + 1
	        oldPoliciesCustom["results"].append(eachPolicy)
	        print ("Custom policy from old configured gw : {}:{}".format(eachPolicy["name"], eachPolicy["version"]))
    print()
	
    if oldPoliciesCustom["total_results"] > 0:
        print("Number of custom policies in the old configured gateway : " + str(oldPoliciesCustom["total_results"]))
        print()
        newPolicies = None
        if spaceName == None:
            print ("Custom policies from NEW configured gateway : {}, catalog : {} and org : {} ::: ".format(newConfGWName, catalogName, orgName))
            newPolicies = runCommand("apic policies:list-all --format yaml --fields name,version,custom --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName, True)
        else:
            print ("Custom policies from NEW configured gateway : {}, space : {} catalog : {} and org : {} ::: ".format(newConfGWName, spaceName, catalogName, orgName))
            newPolicies = runCommand("apic policies:list-all --format yaml --fields name,version,custom --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " --space " + spaceName, True)
        newPolicies = yaml.safe_load(newPolicies)
        print()
        
        newPoliciesCustomList = []
        if newPolicies["total_results"] > 0:
            for eachNewPolicy in newPolicies["results"]:
                if eachNewPolicy["custom"] == True:
                    newPoliciesCustomList.append(eachNewPolicy["name"] + ":" + eachNewPolicy["version"])
        print ("Custom policies already added in the new gateway :: ", newPoliciesCustomList)
        
        for each in oldPoliciesCustom["results"]:
            if each["name"] + ":" + each["version"] in newPoliciesCustomList:
                print ("ACTION OUTPUT : Custom policy({}) ALREADY EXISTS in configured gateway : {}, catalog : {} and org : {} ::: ".format(each["name"] + ":" + each["version"], newConfGWName, catalogName, orgName))
            else:
                #get policy implementation
                if os.path.exists(DATA_TEMP_DIR + "/" + each["name"] + "_" + each["version"] + "_implementation.zip"):
                    os.remove(DATA_TEMP_DIR + "/" + each["name"] + "_" + each["version"] + "_implementation.zip")
                    
                m1 = None
                if spaceName == None:
                    m1 = runCommand("apic policies:implementation --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + oldConfGWName + " " + each["name"] + ":" + each["version"] + " --output " + DATA_TEMP_DIR, False)
                else:
                    m1 = runCommand("apic policies:implementation --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + oldConfGWName + " --space " + spaceName + " " + each["name"] + ":" + each["version"] + " --output " + DATA_TEMP_DIR, False)
        
                #create new custom policy
                m1 = m1.strip()
                zipName = m1[m1.rindex(" ") + 1:]
                if spaceName == None:
                    n1 = runCommand("apic policies:create --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " " + zipName, True)
                    print ("ACTION OUTPUT : Created custom policy in configured gateway : {}, catalog : {} and org : {} ::: {} ".format(newConfGWName, catalogName, orgName, n1))
                else:
                    n1 = runCommand("apic policies:create --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --space " + spaceName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " " + zipName, True)
                    print ("ACTION OUTPUT : Created custom policy in configured gateway : {}, space : {} catalog : {} and org : {} ::: {} ".format(newConfGWName, spaceName, catalogName, orgName, n1))
        print()
    else:
        print ("ACTION OUTPUT : No custom policies found in the old configured gateway : {}".format(oldConfGWName))


def migrateExtensions(scope, orgName, catalogName, spaceName, oldConfGWName, newConfGWName):
    oldExtensions = None
    if spaceName == None:
        print ("Extensions from OLD configured gateway : {}, catalog : {} and org : {} ::: ".format(oldConfGWName, catalogName, orgName))
        oldExtensions = runCommand("apic extensions:list-all --format yaml --fields name,version,extension --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + oldConfGWName, False)
    else:
        print ("Extensions from OLD configured gateway : {}, space : {}, catalog : {} and org : {} ::: ".format(oldConfGWName, spaceName, catalogName, orgName))
        oldExtensions = runCommand("apic extensions:list-all --format yaml --fields name,version,extension --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + oldConfGWName + " --space " + spaceName, False)
    oldExtensions = yaml.safe_load(oldExtensions)
	
    if oldExtensions["total_results"] > 0:
        print("Number of extensions in the old configured gateway : " + str(oldExtensions["total_results"]))
        newExtensions = None
        if spaceName == None:
            print ("Extensions from NEW configured gateway : {}, catalog : {} and org : {} ::: ".format(newConfGWName, catalogName, orgName))
            newExtensions = runCommand("apic extensions:list-all --format yaml --fields name,version --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName, False)
        else:
            print ("Extensions from NEW configured gateway : {}, space : {}, catalog : {} and org : {} ::: ".format(newConfGWName, spaceName, catalogName, orgName))
            newExtensions = runCommand("apic extensions:list-all --format yaml --fields name,version --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " --space " + spaceName, False)
        newExtensions = yaml.safe_load(newExtensions)
        
        newExtensionsList = []
        if newExtensions["total_results"] > 0:
            for eachExtension in newExtensions["results"]:
                newExtensionsList.append(eachExtension["name"] + ":" + eachExtension["version"])
        
        for each in oldExtensions["results"]:
            if each["name"] + ":" + each["version"] in newExtensionsList:
                print ("ACTION OUTPUT : Extension({}) ALREADY EXISTS in configured gateway : {} for catalog, {} and org, {} ::: ".format(each["name"] + ":" + each["version"], newConfGWName, catalogName, orgName))
            else:
                #create new extension
                filePath = DATA_TEMP_DIR + "/extension_" + each["name"] + "_" + each["version"] + "_" + str(random.randint(0, 9999999)) + ".yaml"
                with open(filePath , 'w') as extensionFile:
                    yaml.dump(each["extension"], extensionFile,  default_flow_style=False)
                
                if spaceName == None:
                    n1 = runCommand("apic extensions:create --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " " + filePath, True)
                    print ("ACTION OUTPUT : Created extension in configured gateway, {} for catalog, {} and org, {} ::: {} ".format(newConfGWName, catalogName, orgName, n1))
                else:
                    n1 = runCommand("apic extensions:create --scope " + scope + " -o " + orgName + " -c "+ catalogName + " --space " + spaceName + " --server " + providerOrgServer + " --configured-gateway-service " + newConfGWName + " " + filePath, True)
                    print ("ACTION OUTPUT : Created extension in configured gateway, {} for space, {} catalog, {} and org, {} ::: {} ".format(newConfGWName, spaceName, catalogName, orgName, n1))
        print() 
    else:
        print ("ACTION OUTPUT : No extensions found in the old configured gateway : {}".format(oldConfGWName))    


def getGatewayServices(includeAnalytics):
    if includeAnalytics == True:
        fields = "name,analytics_service_url"
    else:
        fields = "id,title,endpoint,api_endpoint_base,url"
    output = {}
    orgs = runCommand("apic orgs:list --org_type=admin --fields id,name --server " + cloudAdminServer, True)
    orgs = yaml.safe_load(orgs)
    for org in orgs["results"]:
        azones = runCommand("apic availability-zones:list --fields id,name --server " + cloudAdminServer + " --org " + org["name"], True)
        azones = yaml.safe_load(azones)
        for azone in azones["results"]:
            services = runCommand("apic gateway-services:list --fields " + fields + " --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
            services = yaml.safe_load(services)
            for service in services["results"]:
                if includeAnalytics == False:
                    output[service["endpoint"]] = service["id"] +"|" + service["title"] + "|" + service["api_endpoint_base"] + "|" + service["url"]
                else:
                    if "analytics_service_url" in service:
                        output[service["name"]] = service["analytics_service_url"][service["analytics_service_url"].rindex("/")+1:] # id
                    else:
                        output[service["name"]] = "None"
    print ("")
    

    print ("ALL GATEWAY INSTANCES CURRENTLY IN THE TARGET SYSTEM OF CLOUD MANAGER DATABASE :: ")
    i=1
    for e1 in output:
        if includeAnalytics == False:
            dat = output[e1].split("|")
            print (str(i) + ". id : " + dat[0] + "   TITLE : " + dat[1] + "    , ENDPOINT :   " + e1 + "      , API_ENDPOINT_BASE : " + dat[2] + "      and URL : " + dat[3])
        else:
            print (str(i) + ". NAME : " + e1 + "   associated analytics id value : " + output[e1])
        i = i + 1
    print()
    print()
    return output


def getAnalyticsServices():
    output = {}
    orgs = runCommand("apic orgs:list --org_type=admin --fields id,name --server " + cloudAdminServer, True)
    orgs = yaml.safe_load(orgs)
    for org in orgs["results"]:
        azones = runCommand("apic availability-zones:list --fields id,name --server " + cloudAdminServer + " --org " + org["name"], True)
        azones = yaml.safe_load(azones)
        for azone in azones["results"]:
            services = runCommand("apic analytics-services:list --fields id,ingestion_endpoint,name --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
            services = yaml.safe_load(services)
            for service in services["results"]:
                ingestionEP = service["ingestion_endpoint"]
                if ingestionEP.endswith("/ingestion"):
                    ingestionEP = ingestionEP[0:ingestionEP.rindex("/ingestion")]
                output[ingestionEP] =  service["name"] + "^" + azone["name"]
    print ()
    
    print ("ALL ANALYTICS INSTANCES CURRENTLY IN THE TARGET SYSTEM  OF CLOUD MANAGER DATABASE :: ")
    i=1
    for e1 in output:
        print (str(i) + ". name : " + e1 + "   from availability zone name : " + output[e1])
        i = i + 1
    print()
    print()
    return output


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


def removeAPICToolkitTokenFile():
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


def loginToCloudManager():
    global cloudAdminServer
    if args.sso == True:
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
                sys.exit("ERROR : Invalid api_key({}) provided for sso authentication. Exiting...".format(args.api_key))
        else:
            if apiKey == None:
                apiKey = input("Enter the api key value after authentication using sso : ")

        if apiKey != None: apiKey = apiKey.strip()
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


# start
def start():
    print ("CHECKING IF KUBECTL/OC EXIST IN THE PATH AND HAVE ACCESS TO THE CLUSTER :")
    runKubernetesCommand("version", "default")

    print ("CHECKING IF APIC TOOLKIT IN THE PATH :: ")
    runCommand("apic version --accept-license --live-help=false")

    if args.skip_namespace_validation == False:
        validateNamespaces([args.mgmt_ns, args.gw_ns, args.a7s_ns])

    if args.mgmt_ns != None and "|" in args.mgmt_ns:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Invalid namespace({}) provided for management subsystem. Only one namespace need to be provided. Exiting...".format(args.mgmt_ns))
    healthCheck("mgmt", args.mgmt_ns)

    if args.gw_ns == None:
        print ("ACTION OUTPUT : Skipping health check for gateway subsytem as namespace is NOT provided in the input. Given namespace is {}".format(args.gw_ns))
    else:
        multipleNS = args.gw_ns.split("|")
        for ns in multipleNS:
            healthCheck("gw", ns)

    if args.a7s_ns == None:
        print ("ACTION OUTPUT : Skipping health check for analytics subsytem as namespace is NOT provided in the input. Given namespace is {}".format(args.a7s_ns))
    else:
        multipleNS = args.a7s_ns.split("|")
        for ns in multipleNS:
            healthCheck("a7s", ns)

    removeAPICToolkitTokenFile()
    loginToCloudManager()
    updateGatewayInfoInManagementDB()

    print()
    print()
    print()
    print("This script performed the following actions in target APIC system:")
    print("******************************************************************")
    print("1. Checked the health of management and gateway subsystems in the target APIC system.")
    print("2. Checked every provider_org/catalog/space and if configured gateway exists, add the corresponding new configured gateway in target APIC system.")
    print("3. Checked for custom policies, extensions, global polices in each old configured gateway and set on the new configured gateway.")
    print("4. Updated the products published in each catalog to point to the new gateways.")
    print("5. Updated any configured legacy vanity endpoints to point to the new configured gateway service.")
    print("6. Deleted the old configured gateways from every catalog/space in the provider org.")
    print("7. If any default gateways are set in cloud settings of the cloud manager, updated them to point to the new gateway.")
    print("8. Deleted the old gateway service from Cloud manager.")
    print("9. Deleted the old analytics service from the database if configured in the source system.")
    print()
    print("Next steps::")
    print("********************************************")
    print("1. Search for WARNING keyword in the script output and if any found, take necessary action as present in the message.")
    print("2. Run the health_check_post_migration.py script.")
		
	
parser = argparse.ArgumentParser(description="The script is used in form factor to form factor migration. The script is used to update the gateway information in management \
subsystem and republish the products.\n\n\
Prerequisites ::\n\
1. Access to the cluster(target system) using kubectl or oc,\n\
2. Python 3.x and PyYAML module need to be installed\n\
3. Right version of apic toolkit must be in the path to run apic commands\n\
4. The gateway subsystem must be in healthy state.\n\
5. This script MUST be run on the target APIC system AFTER the management database from source system has been restored.\n\
6. This script MUST be run on the target APIC system AFTER the new gateway/portal instance is registered in the Cloud Manager using script or from UI.\n\
7. The credentials for accessing the admin org (cloud manager ui) and provider org(api manager ui) must be available for running the script.\n\
8. The data directory where the configuration from the source system are saved. The data directory with source configuration must be present in the same directory as this script.", 
formatter_class=argparse.RawDescriptionHelpFormatter)


parser.add_argument("-n", "--namespace", dest = "ns", help="uses this namespace value for all subsystems if individual subsystem namespace is not provided. Used for health check")
parser.add_argument("-mgmt_ns", "--management_namespace", dest = "mgmt_ns", help="namespace of the management subsystem used for health check. This has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-gw_ns", "--gateway_namespace", dest = "gw_ns", help="namespace of the gateway subsystem used for health check. If gateways in multiple namespaces, use pipe(|) to separate each namespace. This value has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-a7s_ns", "--analytics_namespace", dest = "a7s_ns", help="namespace of the analytics subsystem used for health check. If analytics in multiple namespaces, use pipe(|) to separate each namespace. This value has more precedence than the common flag, -n or --namespace.")

parser.add_argument("-u", "--username", dest = "username", help="username to login to the cloud manager UI.")
parser.add_argument("-p", "--password", dest = "password", help="password to login to the cloud manager UI.")
parser.add_argument("-s", "--server", dest = "server", help="hostname to connect to cloud manager. Use platform api hostname.")
parser.add_argument("-r", "--realm", dest = "realm", help="name of the realm the user belongs to.")
parser.add_argument("-sso", "--sso", dest = "sso", action='store_true', help="Authentication using sso/oidc.")
parser.add_argument("-api_key", "--api_key", dest = "api_key", help="api key used in sso authentication for cloud manager.")

parser.add_argument('-skip_namespace_validation', "--skip_namespace_validation",  action='store_true', dest = "skip_namespace_validation", help='Skips validation of input namespaces.')

parser.add_argument("-api_manager_hostname", "--api_manager_hostname", dest = "api_manager_hostname", help="hostname of api manager to login using provider org credentials.")
parser.add_argument('-no_migration_user', "--no_migration_user", action='store_true', dest = "no_migration_user", help='The script creates a migration user by default to update the portals and gateways in each provider org and deletes the user at the end. This flag disables migration user creation and in which case the provider org credentials need to be supplied.')

parser.add_argument('-ignore_health_check', "--ignore_health_check", action='store_true', dest = "ignore_health_check", help='ignores health check status for each subsystem and proceeds.')
parser.add_argument('-ignore_version_check', "--ignore_version_check", action='store_true', dest = "ignore_version_check", help='ignores version match between source and target systems.')
parser.add_argument('-silent', "--silent", action='store_true', dest = "silent", help='Does not prompt for provider credentials (reads from file) or other inputs and proceeds silently.')
parser.add_argument('-mgmt_subsys_name', "--mgmt_subsystem_name", dest = "mgmt_subsystem_name", help='If multiple management subsytems present in the configuration, the script will use this.')

args = parser.parse_args()

print ("Start time :", time.asctime())
print ()

print ("Input namespace provided for all subsystems : ", args.ns)
print ("Input provided for management subsystem  namespace : ", args.mgmt_ns)
print ("Input provided for gateway subsystem  namespace : ", args.gw_ns)
print ("Input provided for analytics subsystem  namespace : ", args.a7s_ns)
print ()

print ("Host name to connect to cloud manager(-s or --server flag) : ", args.server)
print ("Realm to which user belongs (-r or --realm flag) : ", args.realm)
print ("Cloud manager UI username (-u or --username flag) : ", args.username)
print ("Cloud manager UI password (-p or --password flag) : ********")
print ("SSO flag (-sso or --sso flag) : ", args.sso)
print ("api key (-api_key or --api_key flag) : ", args.api_key)
print ()

print ("API Manager hostname (-api_manager_hostname or --api_manager_hostname flag) : ", args.api_manager_hostname)
print ("No migration user is used (-no_migration_user or --no_migration_user flag) : ", args.no_migration_user)
print ()

print ("ignore health check status for each subsystem : ", args.ignore_health_check)
print ("Ignore version match check (-ignore_version_check or --ignore_version_check flag) : ", args.ignore_version_check)
print ("silent (-silent or --silent flag) : ", args.silent)
print ("Mangement subsystem name (-mgmt_subsys_name or --mgmt_subsystem_name flag) : ", args.mgmt_subsystem_name)
print ()

forceLogPasswords = os.getenv("FORCE_LOG_PASSWORDS")

if args.mgmt_ns == None:
    print ("management namespace not provided. Checking if the flag -n or --namespace is provided which is applicable for all subsystems.")
    args.mgmt_ns = args.ns

if args.gw_ns == None:
    print ("gateway namespace not provided. Checking if the flag -n or --namespace is provided which is applicable for all subsystems.")
    args.gw_ns = args.ns

if args.a7s_ns == None:
    print ("analytics namespace not provided. Checking if the flag -n or --namespace is provided which is applicable for all subsystems.")
    args.a7s_ns = args.ns

print ("namespace used for management subsystem : ", args.mgmt_ns)
print ("namespace used for gateway subsystem : ", args.gw_ns)
print ("namespace used for analytics subsystem : ", args.a7s_ns)

print ()

if args.server == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Server(-s or --server flag) value are needed to update gateway info in the catalogs. Exiting...")
    
if args.sso == False and (args.realm == None or args.username == None or args.password == None):
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : SSO flag is false. Its username/password based authentication. Realm(-r or --realm flag) , Username(-u or --username flag) and password(-p or --password flag) are needed to update gateway info in the catalogs. Exiting...")

pwd = os.getcwd()
DATA_DIR = pwd + "/data"
DATA_TEMP_DIR = pwd + "/data/temp"

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

if args.silent == True and args.no_migration_user:
    if os.path.exists(PORG_CREDENTIALS_FILE_NAME):
        print ("Found provider org credentials. Loading it")
        text_file = open(PORG_CREDENTIALS_FILE_NAME, "r")
        config1 = text_file.read()
        porg_credentials = yaml.safe_load(config1)
        text_file.close()
    else:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : silent flag is set but provider_org_credentials.yaml file is NOT found in the current difrectory. Exiting...")

# load gateway_portal_mapping.yaml file if it exists
if os.path.exists(GATEWAY_PORTAL_MAPPING_FILENAME):
    print ("gateway_portal_mapping.yaml file exists. Loading it")
    text_file = open(GATEWAY_PORTAL_MAPPING_FILENAME, "r")
    config1 = text_file.read()
    print("gateway and portal mapping : \n", config1)
    gateway_portal_mapping = yaml.safe_load(config1)
    text_file.close()

if os.getenv("SKIP_PORGS_WITH_MISSING_CREDENTIALS") != None and os.getenv("SKIP_PORGS_WITH_MISSING_CREDENTIALS").lower() == "true":
    skipPOrgsWithMissingCredentials = True

if args.no_migration_user == False and (args.api_manager_hostname == None or args.api_manager_hostname == ""):
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Migration user will be used to connect to provider orgs but API manager hostname not provided. Use -api_manager_hostname flag with api manager hostname and try again.")

start()

print()
print ("End time :", time.asctime())