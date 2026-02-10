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
import traceback
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
CONFIG_PORTAL_FILE_NAME = "config_portal.yaml"
config =  None
config_portal =  None

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

deletePortalInfoInCatalogSettingRequest = {
  "portal": {
    "type": "none"
  },
  "application_lifecycle": {}
}

addPortalInfoInCatalogSettingRequest = {
  "portal": {
    "endpoint": "val",
    "portal_service_url": "val",
    "type": "drupal"
  },
  "application_lifecycle": {}
}
apic_resources1 = {
  "orgs": {
    "field_name": "org",
    "fields_in_list_output": "id,name,org_type",
    "additional_params_for_list": "--org_type provider",
  }
}

apic_resources2 = {
    "catalogs": {
      "field_name": "catalog",
      "catalog-settings": {
        "methods": ["get"]
      }
    }
}

targetSystemSpecVersion = None
targetSystemReconciledVersion = None

#key is @org@catalog
#value : org/catalog, site,url,backupid,filename
portalBackupInfo = {}


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
        #create migration user
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
        print ("ACTION OUTPUT : Migration user already exists. url : ", migration_user_url)

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
            print("ACTION OUTPUT : Saving the original owners for provider orgs in file, ", porgOwnersFilename)
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
            if eachOrg["name"] in porg_owners:
                changeOwnerBackToOriginal = {
                    "new_owner_user_url": porg_owners[eachOrg["name"]]
                }
                fname = DATA_TEMP_DIR + "/changeOwnerFor_" + eachOrg["name"] + "_request.yaml"
                with open(fname, 'w') as f1:
                    yaml.dump(changeOwnerBackToOriginal, f1, default_flow_style=False)
                #delete_old_owner MUST be used only in this conditon so that the migration members gets deleted after transferring the ownership to the original one
                runCommand("apic orgs:transfer-owner --delete_old_owner --server " + cloudAdminServer + " " + eachOrg["name"] + " " + fname, True)
                print("ACTION OUTPUT : Changed to original owner for provider org, ", eachOrg["name"])
            else:
                print ("Looks like this provider is added newly and not from the source system. Owner details not found for this provider org, ", eachOrg["name"])
            print()
    print()


def updatePortalInfoInManagementDB():
    global providerOrgServer
    global config_portal
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
    
        
        if "registered_portals" not in managementSubsystemDetails or len(managementSubsystemDetails["registered_portals"]) == 0:
            print ("ACTION OUTPUT : No portals are registered in the management subsystem of the source system. No migration is needed. Exiting...")
            print ("Current time :", time.asctime())
            sys.exit(1)
                 
        portalsFromSouceSystem = managementSubsystemDetails["registered_portals"]
        
        #old_portal_endpoint : new_portal_endpoint
        portalEndpointMap = {}
        #old_portal_endpoint^portal_web_endpoint : new_portal_web_endpoint
        portalEndpointAndWebEPMap = {} #portal_webendpoint not unique
        #old_id : new_id
        portalIDMap = {}
        print()
        print()
        
        i = 1
        print ("Checking the portal instances(from the source system) saved in the data directory")
        print ("*********************************************************************************")
        for key in portalsFromSouceSystem:
            eachPortal = portalsFromSouceSystem[key]
            print(str(i) + ". Checking the portal instance(saved in config file) from the source system with NAME : {}, ENDPOINT : {}, WEB_ENDPOINT : {} ".format(eachPortal["name"], eachPortal["endpoint"], eachPortal["web_endpoint_base"]))  
            i = i + 1
            if "NEW_ENDPOINT" in eachPortal and "NEW_URL" in eachPortal:
                print("NEW PORTAL INSTANCE MATCHING ONE OF THE SOURCE SYSTEM PORTAL. New Portal NAME : {} , ENDPOINT : {}, WEB_ENDPOINT : {}".format(eachPortal["NEW_NAME"], eachPortal["NEW_ENDPOINT"], eachPortal["NEW_WEB_ENDPOINT_BASE"])) 
                portalEndpointMap[eachPortal["endpoint"]] = eachPortal["NEW_ENDPOINT"]
                portalEndpointAndWebEPMap[ eachPortal["endpoint"] + "^" + eachPortal["web_endpoint_base"]] = eachPortal["NEW_WEB_ENDPOINT_BASE"]
                newURL = eachPortal["NEW_URL"]
                portalIDMap[eachPortal["id"]] = newURL[newURL.rindex("/")+1:]
            else:
                print ("ACTION OUTPUT : NEW PORTAL INSTANCE IS 'NOT' PRESENT  IN THE CONFIGURATION for this source system portal")
        print()
        print()
        
        print ("Checking the portal instances(in the target system) cloud manager database")
        print ("**************************************************************************")
        portalServicesInTargetDB = getPortalServices()
        i = 1
        for key1 in portalServicesInTargetDB:
            val = portalServicesInTargetDB[key1].split("|")
            # not a old endpoint which is mapped already, not a already mapped new endpoint, endpoint not present in source system
            # basically found a new portal which is not mapped to old one, so may or may not get mapped to old endpoint in the source system
            if key1 not in portalEndpointMap and key1 not in portalEndpointMap.values() and key1 not in portalsFromSouceSystem:
                #this condition will also come when you run upto registration step, then delete the data directory and then run the steps using same (without factory reset of gw/portal) target system (not a new one) - invalid scenario
                print (str(i) + ". NEW Portal with ID : {}, TITLE : {}, WEB_ENDPOINT : {} and ENDPOINT : {} FOUND".format(val[0], val[1], val[2], key1))
                print ("If this portal represents a new portal instance in the target system and this is going to replace a old portal endpoint, then enter the corrosponding OLD PORTAL ENDPOINT that needs to replaced.")
                print ("If this new portal in target system DOES NOT replace any old portal ENDPOINT, just press enter and proceed")
                oldPortalEndpoint = input("ENTER THE 'OLD PORTAL ENDPOINT' WHICH WILL BE REPLACED BY ABOVE, must start with https://    : ")
                print()
                i = i + 1
                if oldPortalEndpoint != None: oldPortalEndpoint = oldPortalEndpoint.strip()
                if oldPortalEndpoint.startswith("https://") == False:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : invalid value provided for old portal ENDPOINT. The values MUST start with https://")
                if oldPortalEndpoint not in portalsFromSouceSystem:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : invalid value provided. Thje value({}) given is not present in the source system.".format(oldPortalEndpoint))
                portalEndpointMap[oldPortalEndpoint] = key1
                old_id = portalsFromSouceSystem[oldPortalEndpoint]["id"]
                portalIDMap[old_id] = val[0]
                portalEndpointAndWebEPMap[ oldPortalEndpoint + "^" + portalsFromSouceSystem[oldPortalEndpoint]["web_endpoint_base"]] = val[2]
                
        print()
        print()
        
        #find if any old portal that are not mapped
        c5 = 0
        listOfNotMappedPortals = ""
        for key in portalsFromSouceSystem:
            eachPortal = portalsFromSouceSystem[key]
            if key not in portalEndpointMap:
                c5 = c5 + 1
                listOfNotMappedPortals = listOfNotMappedPortals + str(i) + ".title : " + eachPortal["title"] + "    web_endpoint_base : " + eachPortal["web_endpoint_base"] + "    endpoint : "+ eachPortal["endpoint"] + "\n"
        
        print()
        print ("MAPPING BETWEEN OLD PORTAL ID IN SOURCE SYSTEM AND NEW PORTAL ID IN TARGET SYSTEM (portal info in catalogs will be updated based on this)")
        print ("*************************************************************************************************************************************************************")
        i = 1
        for eachOldID in portalIDMap:
            print(str(i) + ". OLD PORTAL ID : {}          and        NEW PORTAL ID : {}".format(eachOldID, portalIDMap[eachOldID]))
            i = i + 1
        print()

        
        print()
        print()
        print ("MAPPING BETWEEN OLD PORTAL DIRECTOR/ENDPOINT IN SOURCE SYSTEM AND NEW PORTAL DIRECTOR/ENDPOINT IN TARGET SYSTEM (portal info in catalogs will be updated based on this)")
        print ("*************************************************************************************************************************************************************")
        i = 1
        for oldEP in portalEndpointMap:
            print(str(i) + ". OLD ENDPOINT : {}          and        NEW ENDPOINT : {}".format(oldEP, portalEndpointMap[oldEP]))
            i = i + 1
        print()


        print()
        print()
        print ("MAPPING BETWEEN OLD PORTAL WEB ENDPOINT IN SOURCE SYSTEM AND NEW PORTAL WEB ENDPOINT IN TARGET SYSTEM (portal info in catalogs will be updated based on this)")
        print ("*************************************************************************************************************************************************************")
        i = 1
        for oldWebEP in portalEndpointAndWebEPMap:
            print(str(i) + ". OLD WEB ENDPOINT : {}          and        NEW WEB ENDPOINT : {}".format(oldWebEP[oldWebEP.index("^")+1:], portalEndpointAndWebEPMap[oldWebEP]))
            i = i + 1
        print()
         
         
        if c5 > 0:
            print ("LIST OF PORTALS FROM SOURCE SYSTEM(OLD PORTALS) THAT NOT MAPPED TO A NEW PORTAL IN THE TARGET SYSTEM:")
            print ("*****************************************************************************************************")
            print (listOfNotMappedPortals)
            print ("These portals if being used in catalogs will be left as it is and will be still referring to the old portal.")
            print()
        
        print()
        print()
        #check once again if all the NEW portals exist in the target system because some we add from config file data
        for eachOldEP in portalEndpointMap:
            if portalEndpointMap[eachOldEP] not in portalServicesInTargetDB:
                newWebEP = None
                for each in portalEndpointAndWebEPMap:
                    if each.startswith(eachOldEP):
                        newWebEP = portalEndpointAndWebEPMap[each]
                        break
                print ("Time when error occurred :", time.asctime())
                sys.exit("NEW portal(ENDPOINT: {} and WEB_ENDPOINT: {}) NOT found in the target system. Exiting...".format(portalEndpointMap[eachOldEP], newWebEP))
        
        
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
            print("ACTION OUTPUT : Migration user will be created and used for migrating the portal data. The user will be deleted at the end.")
            print()
            createMigrationUserData()
            changeOwnerForProviderOrgs(True)
            print()
        else:
            if args.silent:
                print("ACTION OUTPUT : Provider org credentials will be read from provider_org_credentials.yaml file to migrate the portal data.")
            else:
                print("ACTION OUTPUT : User will be prompted to enter credentials for each provider org and used to migrate the portal data.")

        
        if "export_data_for_validation" in managementSubsystemDetails and managementSubsystemDetails["export_data_for_validation"] == True:
            print ("Export data (provider orgs) for validation : ")
            print ("*********************************************")
            resource_dir = DATA_DIR + "/" + managementSubsystemName + "/resources"
            for eachResource in apic_resources1:
                exportResourceData(resource_dir, eachResource, apic_resources1[eachResource], "", None, cloudAdminServer)


        print()
        # Check every catalog and update the portal info if its present.
        print("Start : CHECK AND UPDATE PORTAL INFO IN EACH CATALOG OF ALL THE PROVIDER ORGS :::")
        porgs = runCommand("apic orgs:list --org_type=provider --fields id,name,title --server " + cloudAdminServer, True)
        porgs = yaml.safe_load(porgs)
        for eachPORG in porgs["results"]:
            print()
            pro1 = "Processing provider org : " + eachPORG["title"]
            print(pro1)
            print ("*" * len(pro1))
            print()
            
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
                            print ("Authentication using username/password (credentials must have admin access to provider org) :")
                            porgUsername = input("Enter the username for the provider org, " + eachPORG["title"] + " : ")
                            porgPassword = input("Enter the password for the provider org, " + eachPORG["title"] + " : ")
                            print()
                            print ("Valid realms : ")
                            print (realmsString)
                            print()
                            porgRealm = input("Enter realm name the user belongs to : ")
                        else:
                            print ("Authentication using sso (credentials must have admin access to provider org) :")
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
            
            
            portalInfoForEachCatalog = {}
            print ("")
            print ("Save/load portal info for each catalog (we need to save initially just incase add new portal fails after old portal delete:")
            portalInfoForEachCatalogFileName = DATA_DIR + "/" + managementSubsystemName + "/" + eachPORG["name"] + "_portalInfoForEachCatalog.yaml"
            if os.path.exists(portalInfoForEachCatalogFileName):
                print ("Portal configurations for each org/catalog exists. File name : {}, Loading it.".format(portalInfoForEachCatalogFileName))
                text_file = open(portalInfoForEachCatalogFileName, "r")
                portalInfoForEachCatalog = text_file.read()
                portalInfoForEachCatalog = yaml.safe_load(portalInfoForEachCatalog)
                text_file.close()
            else:
                for eachCatalog in catalogs["results"]:
                    if os.path.exists(DATA_TEMP_DIR + "/CatalogSetting.yaml"):
                        os.remove(DATA_TEMP_DIR + "/CatalogSetting.yaml")
                    catalogSetting = runCommand("apic catalog-settings:get --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --fields portal --server " + providerOrgServer + " --output " + DATA_TEMP_DIR, True)
                    catalogSettingYamlFileName = catalogSetting.split()[1]
                    if os.path.exists(catalogSettingYamlFileName):
                        text_file = open(catalogSettingYamlFileName, "r")
                        catalogSetting = text_file.read()
                        catalogSetting = yaml.safe_load(catalogSetting)
                        text_file.close()
                        if "portal" in catalogSetting:
                            portalInfoForEachCatalog[eachCatalog["name"]] = catalogSetting["portal"]
                    else:
                        print ("Time when error occurred :", time.asctime())
                        sys.exit("ERROR : CatalogSetting.yaml file NOT found. Exiting...")
                #save file
                with open(portalInfoForEachCatalogFileName, 'w') as f1:
                    yaml.dump(portalInfoForEachCatalog, f1,  default_flow_style=False)
                
                if "export_data_for_validation" in managementSubsystemDetails and managementSubsystemDetails["export_data_for_validation"] == True:
                    print ("\nExport data (catalogs and catalog settings) for validation :")
                    print ("************************************************************")
                    dir1 = DATA_DIR + "/" + managementSubsystemName + "/resources/orgs"
                    for eachResource in apic_resources2:
                        exportResourceData(dir1, eachResource, apic_resources2[eachResource], " --org " + eachPORG["name"], eachPORG["name"], providerOrgServer)
            
            print ("")
            print ("When this script is run for the first time, state of portal data for all catalogs in the org, {} ::::\n  {} ".format(eachPORG["title"], portalInfoForEachCatalog))
            print ("")
            for eachCatalog in catalogs["results"]:
                cat1 = "Checking portal info in catalog with title : " + eachCatalog["title"] +" and provider org : " + eachPORG["title"]
                print (cat1) 
                print("#" * len(cat1))
                
                if os.path.exists(DATA_TEMP_DIR + "/" + "CatalogSetting.yaml"):
                    os.remove(DATA_TEMP_DIR + "/" + "CatalogSetting.yaml")
                catalogSetting = runCommand("apic catalog-settings:get --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --fields portal --server " + providerOrgServer + " --output " + DATA_TEMP_DIR, True)
                catalogSettingYamlFileName = catalogSetting.split()[1]
                if os.path.exists(catalogSettingYamlFileName):
                    text_file = open(catalogSettingYamlFileName, "r")
                    catalogSetting = text_file.read()
                    catalogSetting = yaml.safe_load(catalogSetting)
                    text_file.close()
                    

                    catalogSettingPortalEndpoint = None
                    portal_id = None
                    if "portal" in catalogSetting and "endpoint" in catalogSetting["portal"] and catalogSetting["portal"]["endpoint"]:
                        catalogSettingPortalEndpoint = catalogSetting["portal"]["endpoint"]
                        portal_id = catalogSetting["portal"]["portal_service_url"].strip()
                        portal_id = portal_id[portal_id.rindex("/")+1:]
                    else:
                        #reading portal info from saved configuration when the script was run for first time
                        catalogSettingPortalInfo = portalInfoForEachCatalog[eachCatalog["name"]]
                        if "type" in catalogSettingPortalInfo and catalogSettingPortalInfo["type"] == "drupal" and "endpoint" in catalogSettingPortalInfo and catalogSettingPortalInfo["endpoint"]:
                            catalogSettingPortalEndpoint = catalogSettingPortalInfo["endpoint"]
                            portal_id = catalogSettingPortalInfo["portal_service_url"].strip()
                            portal_id = portal_id[portal_id.rindex("/")+1:]


                    if portal_id != None:
                        alreadyUpdated = False
                        for eachPortalId in portalIDMap.values():
                            if portal_id == eachPortalId:
                                portalBackupInfo["@" + eachPORG["name"] + "@" + eachCatalog["name"]] = {
                                    "org_catalog": eachPORG["name"] + "/" + eachCatalog["name"],
                                    "site_url": catalogSettingPortalEndpoint
                                }
                                print ("ACTION OUTPUT : Portal info is already updated/referring to NEW portal in the catalog({}) and PORTAL DETAILS ::  id : {} and portal site url : {} ".format(eachCatalog["title"], portal_id, catalogSettingPortalEndpoint) )
                                print()
                                alreadyUpdated = True
                                break
                        
                        if alreadyUpdated == False:
                            mappingFoundFromOldToNew = False
                            if portal_id in portalIDMap:
                                print ("Mapping from old to new portal FOUND, old portal id : {} and new portal id : {}".format(portal_id, portalIDMap[portal_id]))
                                mappingFoundFromOldToNew = True
                            
                            if mappingFoundFromOldToNew:
                                f3 = DATA_TEMP_DIR + "/" + "deletePortalInfoInCatalogSettingRequest.yaml"
                                with open(f3, 'w') as deletePortalFromCatalogFile:
                                    yaml.dump(deletePortalInfoInCatalogSettingRequest, deletePortalFromCatalogFile,  default_flow_style=False)
                                runCommand("apic catalog-settings:update --force --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --server " + providerOrgServer + " " + f3, False)
                                print("Deleted old portal info for the org : {} and catalog : {}".format(eachPORG["title"], eachCatalog["title"]))
                                time.sleep(15)
                                
                                print()
                                site_url = None
                                isStandardSiteURL = False
                                old_key = None
                                for each in portalEndpointAndWebEPMap:
                                    webEP = each[each.index("^")+1:]
                                    if catalogSettingPortalEndpoint.startswith(webEP):
                                        old_key = each
                                        isStandardSiteURL = True
                                        break

                                if isStandardSiteURL:
                                    oldep = urlparse(catalogSettingPortalEndpoint)
                                    newEP = portalEndpointAndWebEPMap[old_key]
                                    site_url = newEP + oldep.path
                                else:
                                    site_url = catalogSettingPortalEndpoint

                                portal_service_url = "https://" + providerOrgServer + "/api/orgs/" + eachPORG["id"] + "/portal-services/" + portalIDMap[portal_id]
                        
                                addPortalInfoInCatalogSettingRequest["portal"]["endpoint"] = site_url
                                addPortalInfoInCatalogSettingRequest["portal"]["portal_service_url"] = portal_service_url
                                
                                f4 = DATA_TEMP_DIR + "/" + "addPortalInfoInCatalogSettingRequest.yaml"
                                with open(f4, 'w') as addPortalToCatalogFile:
                                    yaml.dump(addPortalInfoInCatalogSettingRequest, addPortalToCatalogFile,  default_flow_style=False)
                                print ("Input body to add to new portal : ", addPortalInfoInCatalogSettingRequest)
                                runCommand("apic catalog-settings:update --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --server " + providerOrgServer + " " + f4, False)
                                
                                if os.path.exists(DATA_TEMP_DIR + "/" + "CatalogSetting.yaml"):
                                    os.remove(DATA_TEMP_DIR + "/" + "CatalogSetting.yaml")
                                updatedCatalogSetting = runCommand("apic catalog-settings:get --org " + eachPORG["name"] + " --catalog "+ eachCatalog["name"] + " --fields portal --server " + providerOrgServer + " --output " + DATA_TEMP_DIR, True)
                                catalogSettingYamlFileName = updatedCatalogSetting.split()[1]
                                if os.path.exists(catalogSettingYamlFileName):
                                    text_file = open(catalogSettingYamlFileName, "r")
                                    updatedCatalogSetting = text_file.read()
                                    updatedCatalogSetting = yaml.safe_load(updatedCatalogSetting)
                                    text_file.close()
                                
                                portalBackupInfo["@" + eachPORG["name"] + "@" + eachCatalog["name"]] = {
                                    "org_catalog": eachPORG["name"] + "/" + eachCatalog["name"],
                                    "site_url": site_url
                                }
                                
                                print("ACTION OUTPUT : Added new portal info for the org : {}, catalog : {} and catalog setting portal info :: {} ".format(eachPORG["title"], eachCatalog["title"], updatedCatalogSetting["portal"]))
                                time.sleep(5)
                                print()
                            else:
                                print ("ACTION OUTPUT : No mapping found for this portal endpoint : {}. Leaving the portal as it is in the catalog : {} and org : {}".format(catalogSettingPortalEndpoint, eachCatalog["title"], eachPORG["title"]))
                                if len(portalEndpointMap) == 0:
                                    #can be DR scenario or portal being migrated later, generate backup info
                                    #we need backup info for DR scenario
                                    portalBackupInfo["@" + eachPORG["name"] + "@" + eachCatalog["name"]] = {
                                        "org_catalog": eachPORG["name"] + "/" + eachCatalog["name"],
                                        "site_url": catalogSettingPortalEndpoint
                                    }



                    else:
                        print ("ACTION OUTPUT : No portal configuration found in catalog with title : " + eachCatalog["title"])
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
        # delete the old portal services
        print ("Delete source system portals::::")
        print ("********************************")
        m = 1
        foundOldPortals = False
        for key in portalServicesInTargetDB:
            da1 = portalServicesInTargetDB[key].split("|")
            if key in portalsFromSouceSystem:
                foundOldPortals = True
                print (str(m) + ". The portal (title : {}, web endpoint : {}) from source system".format(da1[1], da1[2]))
                m = m + 1
                if key not in portalEndpointMap:
                    print ("   The portal (title : {}, web endpoint : {}) from source system is NOT mapped to any new portal in the target system".format(da1[1], da1[2]))
                    print ("   It's assumed that the old portal will be still used from the target APIC system or it will be migrated later.")
                    print ("   Not deleting the portal. If the portal has to be deleted, it has to be manually removed from the catalogs where its used and then deleted from cloud manager/topology.")
                    continue
                    
                id1 = da1[0]
                azoneid = portalsFromSouceSystem[key]["availability_zone_url"]
                azoneid = azoneid[azoneid.rindex("/") + 1:].strip()
                runCommand("apic portal-services:delete --force --server " + cloudAdminServer + " --org admin --availability-zone " + azoneid + " " + id1, False)
                print ("ACTION OUTPUT : Deleted the old portal service which is from the source system, title : {}, web endpoint : {}, endpoint : {}  ".format(da1[1], da1[2], key))
                print()
        if foundOldPortals == False:
            print ("All old portals are already deleted.")
        

        print()
        registeredPortalsInTarget = getPortalServices()
        flag = True
        loopCount = 0
        timedOut = False
        while flag:
            loopCount = loopCount + 1
            if loopCount >= 120:
                flag = False
                timedOut = True
                print ("Timeout after Waiting for portal site(s) creation.")
                break # safe break after approximate 4+ hours
            print()
            print()
            m = 1
            notReadyStateFound = False
            for eachPortalEP in registeredPortalsInTarget:
                if eachPortalEP in portalEndpointMap.values() and eachPortalEP not in portalEndpointMap:
                    eachPortal = registeredPortalsInTarget[eachPortalEP]
                    portalName = eachPortal.split("|")[3]
                    allportalSites = None
                    try:
                        allportalSites = runCommand("apic --mode portaladmin sites:list --format yaml --server " + cloudAdminServer + " --portal_service_name " + portalName, True, 0, False)
                        #removing 0 date before laoding
                        if allportalSites != None and allportalSites.startswith("Error") == False:
                            splitData = allportalSites.splitlines()
                            for i in range(len(splitData)):
                                splitData[i] = splitData[i].strip()
                                if splitData[i].startswith("snapshot_first_requested"):
                                    splitData[i] = "snapshot_first_requested: ''"
                                if splitData[i].startswith("-") == False:
                                    splitData[i] = "  " + splitData[i]
                            allportalSites = "\n".join(splitData)
                            allportalSites = yaml.safe_load(allportalSites)
                        else:
                            print("list sites output  : ", allportalSites)
                    except:
                        allportalSites = None
                        traceback.print_exc()
                        notReadyStateFound = True
                    
                    if allportalSites != None:
                        print()
                        header = "Portal Site URL" + (" " * (100 - len("Portal Site URL"))) + "Status"
                        print(header)
                        print("*" * len(header))
                        for eachSite in allportalSites:
                            v = 100 - len(eachSite["url"])
                            status = None
                            if eachSite["state"] == "INSTALLED" and eachSite["subscribed_to_webhooks"] == True and eachSite["check_state"] == "OK: 200":
                                status = "Ready (state=" + eachSite["state"] + ", subscribed_to_webhooks=" + str(eachSite["subscribed_to_webhooks"]) + ", check_state=" + eachSite["check_state"] +")"
                            else:
                                notReadyStateFound = True
                                status = "Not Ready (state=" + eachSite["state"] + ", subscribed_to_webhooks=" + str(eachSite["subscribed_to_webhooks"]) + ", check_state=" + eachSite["check_state"] +")"
                            print (str(m) +". " + eachSite["url"] + (" " * v) + status)
                            m = m + 1
                        print()
                        print()
            
            if notReadyStateFound == False:
                flag = False
            else:
                print()
                print ("Waiting for portal site(s) creation, check every 3 minutes. current time : ", time.asctime())
                print ("Time taken depends on number of portal sites to be created, disk performance, whether it's n1 or n3 profiles etc.")
                time.sleep(180)
                print()
                print()

        
        print()
        print()
        if timedOut == True:
            print("ACTION OUTPUT : The script has timed out waiting for portal sites to come to ready state.")
            print("ACTION OUTPUT : Manually check the status of portal sites and once the sites are ready, perform the restore sites steps as mentioned below.")
        else:
            print ("ACTION OUTPUT : All the portal sites are in ready state. Proceed for next steps of restoring the portal sites using the backups taken from source system.")

        
        print()
        print()
        print("portalBackupInfo ask :: ", portalBackupInfo)
        print()
        print()
        for eachPortalEndpoint in registeredPortalsInTarget:
            pdata = registeredPortalsInTarget[eachPortalEndpoint].split("|")
            eachPortalWebEndpoint = pdata[2]
            # only for new portals which are mapped from a old one
            if eachPortalWebEndpoint not in portalEndpointAndWebEPMap.values():
                if len(portalEndpointAndWebEPMap) != 0:
                     # some mapping present, but not for this portal
                     # if no mapping present meaning len(portalEndpointAndWebEPMap) == 0:, it can be a DR scenario or portal being migrated later
                     # we need backup info for DR scenario
                     continue

            keyName = None
            if args.dont_use_toolkit_for_portal_backup:
                allbackupInfo = runKubernetesCommand("get portalbackups.portal.apiconnect.ibm.com -o yaml", args.ptl_ns, True)
                keyName = "items"
            else:
                allbackupInfo = runCommand("apic --mode portaladmin backups:list --server " + cloudAdminServer + " --portal_service_name " + pdata[3], True, 2, False)
                keyName = "backups"

            # for other portal in different ns? todo
            if allbackupInfo != None and allbackupInfo != "" and "No remote backups found" not in allbackupInfo:
                allbackupInfo = yaml.safe_load(allbackupInfo)
                backupItems = allbackupInfo[keyName]

                #see if it can be improved later
                for eachSubsysName in config_portal["portal_subsystem"].keys():
                    if "backupId_sites" in config_portal["portal_subsystem"][eachSubsysName]:
                        for eachBackupIdSaved in config_portal["portal_subsystem"][eachSubsysName]["backupId_sites"]:
                            processedOneSavedBackup = False
                            for each in backupItems:
                                flagCondition = False
                                neededBackupFilename = None
                                if args.dont_use_toolkit_for_portal_backup:
                                    flagCondition = each["spec"]["type"] == "site" and eachBackupIdSaved in each["status"]["fullBackupName"]
                                    neededBackupFilename = each["status"]["fullBackupName"]
                                else:
                                    flagCondition = eachBackupIdSaved in each
                                    neededBackupFilename = each

                                if flagCondition:
                                    orgCatalogInFilename = False
                                    for eachOrgCat in portalBackupInfo:
                                        portalBackupName = eachOrgCat + "-" + eachBackupIdSaved
                                        if portalBackupName in neededBackupFilename:
                                            orgCatalogInFilename = True
                                            portalBackupInfo[eachOrgCat]["backupFileName"] = neededBackupFilename
                                            portalBackupInfo[eachOrgCat]["backupId"] = eachBackupIdSaved
                                            portalBackupInfo[eachOrgCat]["subsystemName"] = eachSubsysName
                                            processedOneSavedBackup = True
                                            break
                                    if orgCatalogInFilename == False: # custom url used in portal site
                                        for e1 in portalBackupInfo:
                                            eachData = portalBackupInfo[e1]
                                            if "backupFileName" not in eachData:
                                                siteurl = eachData["site_url"][8:] # without https://
                                                siteurl = siteurl.replace("/", "@")
                                                if neededBackupFilename.startswith(siteurl):
                                                    portalBackupInfo[e1]["backupFileName"] = neededBackupFilename
                                                    portalBackupInfo[e1]["backupId"] = eachBackupIdSaved
                                                    portalBackupInfo[e1]["subsystemName"] = eachSubsysName
                                if processedOneSavedBackup: break

        a1 = 25 - len("Subsystem Name")
        a2 = 30 - len("Org/Catalog")
        a3 = 20 - len("Backup Id")

        print("Note : The portal sites will take some time to create(depending on the number of portal sites). Access the portal sites only after that portal sites are ready.")
        print()
        print()
        print("Portal site backups to be restored on the portal system:")
        print("********************************************************")
        if len(portalBackupInfo) == 0:
            print("ACTION OUTPUT : No portal site backups found.")
        else:
            print()
            print ("Subsystem Name" + (" " * a1) + "Org/Catalog" + (" "*a2) + "Backup Id" + (" "*a3) + "Backup Filename (site_url)")
            print("*" * 101)
            for each in portalBackupInfo.values():
                if "subsystemName" in each:
                    if each["subsystemName"] in config_portal["portal_subsystem"]:
                        if "backupInfo" not in config_portal["portal_subsystem"][each["subsystemName"]]:
                            config_portal["portal_subsystem"][each["subsystemName"]]["backupInfo"] = {}
                        config_portal["portal_subsystem"][each["subsystemName"]]["backupInfo"][each["backupId"]] = each["backupFileName"] + "|" + each["site_url"]

                    a1 = 25 - len(each["subsystemName"])
                    a2 = 30 - len(each["org_catalog"])
                    a3 = 0
                    if len(each["backupId"]) > 20:
                       a3 = 3
                    else:
                        a3 =  20 - len(each["backupId"])
                    print (each["subsystemName"] + (" "*a1) + each["org_catalog"] + (" "*a2) + each["backupId"] + (" "*a3) + each["backupFileName"] + " (" + each["site_url"] + ")")
            
            with open(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME, 'w') as configPortalFile:
                yaml.dump(config_portal, configPortalFile, default_flow_style=False)

        print()
        print()
        print()
        print("This script performed the following actions in the target APIC system:")
        print("**********************************************************************")
        print("1. Checked the health of management and portal subsystems in the target APIC system.")
        print("2. Checked every provider_org/catalog and if portal exists update it to point to the new portal service in target APIC system.")
        print("3. Deleted the old portal service from Cloud manager.")
        print("4. Wait until all the portal sites are ready.")
        print("5. Generate report will list the portal backup ids, backup file names and portal_site url which can be used for manual restore.")
        print()
        print("Next steps:: Restore portal sites")
        print("*****************************************")
        print("Two options to restore portal sites")
        print("1. Restore portal sites using script ::")
        print("    Use the restore_portal_db.py script to restore the portal sites. This uses the portal restore CR.")
        print()
        print("2. Restore portal sites manually ::")
        print("    -  If the portal site backups need to be restored manually, connect to portal admin pod and restore the backup files listed above using commands below.")
        print("    -  Command to list the site backups : remote_transfer_backup -l")
        print("    -  Command to download each site backup : remote_transfer_backup -d <SITE_BACKUP_FILENAME>")
        print("    -  Command to restore each site backup : restore_site -f -u <SITE_URL> <SITE_BACKUP_FILENAME>")
        print()
                
        
def getPortalServices():
    output = {}
    orgs = runCommand("apic orgs:list --org_type=admin --fields id,name --server " + cloudAdminServer, True)
    orgs = yaml.safe_load(orgs)
    for org in orgs["results"]:
        azones = runCommand("apic availability-zones:list --fields id,name --server " + cloudAdminServer + " --org " + org["name"], True)
        azones = yaml.safe_load(azones)
        for azone in azones["results"]:
            services = runCommand("apic portal-services:list --fields id,name,title,endpoint,web_endpoint_base --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
            services = yaml.safe_load(services)
            for service in services["results"]:
                output[service["endpoint"]] = service["id"] +"|" + service["title"] + "|" + service["web_endpoint_base"] + "|" + service["name"]
    print ("")
    
    print ("ALL PORTAL INSTANCES CURRENTLY IN THE TARGET SYSTEM OF CLOUD MANAGER DATABASE :: ")
    i=1
    for e1 in output:
        dat = output[e1].split("|")
        print (str(i) + ". id : " + dat[0] + "   TITLE : " + dat[1] + "   NAME : " + dat[3] + "    , ENDPOINT :   " + e1 + "      and WEB_ENDPOINT : " + dat[2])
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
        validateNamespaces([args.mgmt_ns, args.ptl_ns])

    if args.mgmt_ns != None and "|" in args.mgmt_ns:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Invalid namespace({}) provided for management subsystem. Only one namespace need to be provided. Exiting...".format(args.mgmt_ns))
    healthCheck("mgmt", args.mgmt_ns)
    
    if args.ptl_ns == None:
        print ("ACTION OUTPUT : Skipping health check for portal subsytem as namespace is NOT provided in the input. Given namespace is {}".format(args.ptl_ns))
    else:
        multipleNS = args.ptl_ns.split("|")
        for ns in multipleNS:
            healthCheck("ptl", ns)

    removeAPICToolkitTokenFile()
    loginToCloudManager()
    updatePortalInfoInManagementDB()
		
		
	
parser = argparse.ArgumentParser(description="The script is used in form factor to form factor migration. The script is used to update the old portal site information in management \
subsystem and point to the new portal instance.\n\n\
Prerequisites ::\n\
1. Access to the cluster(target system) using kubectl or oc,\n\
2. Python 3.x and PyYAML module need to be installed\n\
3. Right version of apic toolkit must be in the path to run apic commands\n\
4. The portal subsystem must be in healthy state.\n\
5. This script MUST be run on the target APIC system AFTER the management database from source system has been restored.\n\
6. This script MUST be run on the target APIC system AFTER the new gateway/portal instance is registered in the Cloud Manager using script or from UI.\n\
7. The credentials for accessing the admin org (cloud manager ui) and provider org(api manager ui) must be available for running the script.\n\
8. The data directory where the configuration from the source system are saved. The data directory with source configuration must be present in the same directory as this script.", 
formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument("-n", "--namespace", dest = "ns", help="uses this namespace value for all subsystems if individual subsystem namespace is not provided. Used for health check")
parser.add_argument("-mgmt_ns", "--management_namespace", dest = "mgmt_ns", help="namespace of the management subsystem used for health check. This has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-ptl_ns", "-portal_namespace", dest = "ptl_ns", help="namespace of the portal subsystem used for health check. If portals in multiple namespaces, use pipe(|) to separate each namespace. This value has more precedence than the common flag, -n or --namespace.")

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
parser.add_argument('-ptl_subsys_name', "--ptl_subsystem_name", dest = "ptl_subsystem_name", help='If multiple portal subsytems present in the configuration, the script will use this.')

parser.add_argument('-dont_use_toolkit_for_portal_backup', "--dont_use_toolkit_for_portal_backup", action='store_true', dest = "dont_use_toolkit_for_portal_backup", help='If this flag is used, portal backups are obtained using kubectl get portalbackups command. Default it uses apic --mode portaladmin backups:list to get portal backups. Use this flag when only DR(no change in endpoints) is performed.')

args = parser.parse_args()

print ("Start time :", time.asctime())
print ()

print ("Input namespace provided for all subsystems (-n or --namespace flag) : ", args.ns)
print ("Input namespace provided for management subsystem (-mgmt_ns or --management_namespace flag) : ", args.mgmt_ns)
print ("Input namespace provided for portal subsystem (-ptl_ns or --portal_namespace flag) : ", args.ptl_ns)
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

print ("ignore health check status for each subsystem (-ignore_health_check or --ignore_health_check flag) : ", args.ignore_health_check)
print ("Ignore version match check (-ignore_version_check or --ignore_version_check flag) : ", args.ignore_version_check)
print ("silent (-silent or --silent flag) : ", args.silent)
print ("Mangement subsystem name (-mgmt_subsys_name or --mgmt_subsystem_name flag) : ", args.mgmt_subsystem_name)
print ("Portal subsystem name (-ptl_subsys_name or --ptl_subsystem_name flag) : ", args.ptl_subsystem_name)
print ()

print ("Dont use toollkit for getting portal backups (-dont_use_toolkit_for_portal_backup or --dont_use_toolkit_for_portal_backup flag) : ", args.dont_use_toolkit_for_portal_backup)

forceLogPasswords = os.getenv("FORCE_LOG_PASSWORDS")

if args.mgmt_ns == None:
    print ("management namespace not provided. Checking if the flag -n or --namespace is provided which is applicable for all subsystems.")
    args.mgmt_ns = args.ns

if args.ptl_ns == None:
    print ("portal namespace not provided. Checking if the flag -n or --namespace is provided which is applicable for all subsystems.")
    args.ptl_ns = args.ns

print ("namespace used for management subsystem : ", args.mgmt_ns)
print ("namespace used for portal subsystem : ", args.ptl_ns)
print ()


if args.server == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Server(-s or --server flag) value are needed to update portal info in the catalogs. Exiting...")
    
if args.sso == False and (args.realm == None or args.username == None or args.password == None):
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : SSO flag is false. Its username/password based authentication. Realm(-r or --realm flag) , Username(-u or --username flag) and password(-p or --password flag) are needed to update portal info in the catalogs. Exiting...")

pwd = os.getcwd()
DATA_DIR = pwd + "/data"
DATA_TEMP_DIR = pwd + "/data/temp"

# load config data if exists
if os.path.exists(DATA_DIR + "/" + CONFIG_FILE_NAME):
    print ("Source APIC system configuration file exists. Loading it")
    text_file = open(DATA_DIR + "/" + CONFIG_FILE_NAME, "r")
    config1 = text_file.read()
    print("Management configuration file : ", config1)
    config = yaml.safe_load(config1)
    text_file.close()
else:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : config.yaml file with details of the source APIC system in NOT present in the data directory. Exiting...")
    

# load portal config data if exists
if os.path.exists(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME):
    print ("Source APIC system portal configuration file exists. Loading it")
    text_file = open(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME, "r")
    config1 = text_file.read()
    print("portal configuration file : ", config1)
    config_portal = yaml.safe_load(config1)
    text_file.close()
else:
    print ("Current time  :", time.asctime())
    sys.exit("ACTION OUTPUT : portal_config.yaml file NOT present. Source APIC system does not have portal subsystem installed. No migration/portal updates needed in the restored management database. Exiting...")
    
    
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
    
if os.getenv("SKIP_PORGS_WITH_MISSING_CREDENTIALS") != None and os.getenv("SKIP_PORGS_WITH_MISSING_CREDENTIALS").lower() == "true":
    skipPOrgsWithMissingCredentials = True

if args.no_migration_user == False and (args.api_manager_hostname == None or args.api_manager_hostname == ""):
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Migration user will be used to connect to provider orgs but API manager hostname not provided. Use -api_manager_hostname flag with api manager hostname and try again.")

start()

print()
print ("End time :", time.asctime())