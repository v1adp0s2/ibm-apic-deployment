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

subsystems = ("mgmt", "ptl", "gw", "a7s")
ns = []

oc_client = "oc"
kubectl_client = "kubectl"
client = oc_client

pwd = None
DATA_DIR = None
DATA_TEMP_DIR = None
CONFIG_FILE_NAME = "config.yaml"
config = None

mgmtSubsystemName = None
cloudAdminServer = None
forceLogPasswords = None

apic_resources1 = {
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

apic_resources2 = {
  "orgs": {
    "field_name": "org",
    "fields_in_list_output": "id,name,org_type",
    "additional_params_for_list": "--org_type provider",
  }
}

apic_resources3 = {
    "catalogs": {
      "field_name": "catalog",
      "catalog-settings": {
        "methods": ["get"]
      }
    }
}

# catalog scope
apic_resources4 = {
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
apic_resources5 = {
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


# checkSubsystemHealth
def checkSubsystemHealth():
    global mgmtSubsystemName
    for i in range(4):
        if subsystems[i] == "mgmt" and  ns[i] == None:
            print ("ACTION OUTPUT : Skipping management subsystem because management namespace is NOT provided in the input.")
            print()
            continue;
        elif subsystems[i] == "ptl" and ns[i] == None:
            print ("ACTION OUTPUT : Skipping portal subsystem because portal namespace is NOT provided in the input.")
            print()
            continue;
        elif subsystems[i] == "gw" and ns[i] == None:
            print ("ACTION OUTPUT : Skipping gateway subsystem because gateway namespace is NOT provided in the input.")
            print()
            continue;
        elif subsystems[i] == "a7s" and ns[i] == None:
            print ("ACTION OUTPUT : Skipping analytics subsystem because analytics namespace is NOT provided in the input.")
            print()
            continue;

        subsystemName = None
        giveNNamespacesForSubsystemType = ns[i].split("|")
        for eachNamespace in giveNNamespacesForSubsystemType:
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

                # check health
                print ("Phase : {} and state : {} for {} subsystem, {}".format(crData["status"]["phase"], crData["status"]["state"], subsystems[i], subsystemName))
                state = crData["status"]["state"]
                if crData["status"]["phase"] != "Running" or state[0:state.index("/")] != state[state.index("/") + 1:]:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Health check failed for {} subsystem with name {}. Phase : {} and state : {}".format(subsystems[i], subsystemName, crData["status"]["phase"], crData["status"]["state"]))
                print ("ACTION OUTPUT : {} subsytem with name {} is healthy".format(subsystems[i], subsystemName))
                print ()
        

def getWebhookStatus():
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
    cloudWebhookReport.append("GATEWAY/PORTAL SERVICES WEBHOOKS (cloud level) ::")
    cloudWebhookReport.append("*************************************************")
    
    catalogGatewayWebhookReport = []
    headerAdded2 = False
    catalogGatewayWebhookReport.append("CONFIGURED GATEWAY SERVICES (CATALOGS) WEBHOOKS ::")
    catalogGatewayWebhookReport.append("**************************************************")
    
    catalogPortalWebhookReport = []
    headerAdded3 = False
    catalogPortalWebhookReport.append("CONFIGURED PORTAL SERVICES (CATALOGS) WEBHOOKS ::")
    catalogPortalWebhookReport.append("*************************************************")
    
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
            elif "portal_service_url" in webhook:
                pid = webhook["portal_service_url"][webhook["portal_service_url"].rindex("/") + 1:]
                if pid in portals:
                    i = 50 - len(portals[pid])
                    cloudWebhookReport.append(pid + " (portal)     " + portals[pid] + (" " * i) + webhook["state"] + (" " * j) + webhook["id"])
        
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


def checkStatusOfPortalSites():
    print("Check status of portal sites::")

    mgmtSubsystemDetails = config["management_subsystem"][mgmtSubsystemName]
    if "registered_portals" in mgmtSubsystemDetails:
        registeredPortalsinSourceSystem = mgmtSubsystemDetails["registered_portals"]

    registeredPortalsInTarget = getPortalServices()
    if len(registeredPortalsInTarget) > 0:
        flag = True
        loopCount = 0
        timedOut = False
        while flag:
            loopCount = loopCount + 1
            if loopCount >= 60:
                flag = False
                timedOut = True
                print ("Timeout while waiting to check the status of portal sites.")
                break # safe break after approximate 2 hours
            print()
            print()
            m = 1
            notReadyStateFound = False
            for portalEP in registeredPortalsInTarget:
                #health check only for migrated portals. for other portals still no data on the new portal subsystems
                if portalEP in registeredPortalsinSourceSystem and "NEW_ENDPOINT" not in registeredPortalsinSourceSystem[portalEP]:
                    continue
                eachPortal = registeredPortalsInTarget[portalEP]
                portalName = eachPortal.split("|")[3]
                allportalSites = None
                try:
                    allportalSites = runCommand("apic --mode portaladmin sites:list --format yaml --server " + cloudAdminServer + " --portal_service_name " + portalName, True, 0, False)
                    if allportalSites.lower().startswith("error") == False:
                        #removing 0 date before laoding
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
                        allportalSites = None
                except:
                    allportalSites = None
                    traceback.print_exc()
                    notReadyStateFound = True

                if allportalSites != None and len(allportalSites) > 0:
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
                            webhook_status = ""
                            if "subscribed_to_webhooks" in eachSite: webhook_status = eachSite["subscribed_to_webhooks"] # subscribed_to_webhooks was not present 
                            status = "Not Ready (state=" + eachSite["state"] + ", subscribed_to_webhooks=" + str(webhook_status) + ", check_state=" + eachSite["check_state"] +")"
                        print (str(m) +". " + eachSite["url"] + (" " * v) + status)
                        m = m + 1

            if notReadyStateFound == False:
                flag = False
            else:
                print()
                print ("Waiting for portal site(s) to be healthy, check every 2 minutes. current time : ", time.asctime())
                time.sleep(120)
                print()
                print()

        print()
        print()
        if timedOut == True:
            print("ACTION OUTPUT : The script has timed out waiting for portal sites to come to ready state.")
            print("ACTION OUTPUT : Manually check the status of portal sites and once the sites are ready.")
        else:
            print ("ACTION OUTPUT : All the migrated portal sites are in ready state no portal sites found.")

        print()
        print()
    else:
        print("ACTION OUTPUT : No portal sites found in the target apic system.")

def validateWithSourceSystemExportedData():
    if mgmtSubsystemName == None:
        print("ACTION OUTPUT : Could not validate target system data with data from source system. Management namespace not provided or subsystem not installed.")
        return
    
    if "export_data_for_validation" in config["management_subsystem"][mgmtSubsystemName] and config["management_subsystem"][mgmtSubsystemName]["export_data_for_validation"] == True:    
        print ("Validate target data with exported data from source system :::")
        print ("***************************************************************")
        print("Validate admin org, availability zones and gateway,portal/analytucs services:")
        resource_dir = DATA_DIR + "/" + mgmtSubsystemName + "/resources"
        for eachResource in apic_resources1:
            validateData(resource_dir, eachResource, apic_resources1[eachResource], "", None, cloudAdminServer)
        
        print("Validate provider orgs:")
        for eachResource2 in apic_resources2:
            validateData(resource_dir, eachResource2, apic_resources2[eachResource2], "", None, cloudAdminServer)
        

        print ("Validate catalogs and catalog settings in each provider org:")
        # porgs = runCommand("apic orgs:list --org_type=provider --fields id,name --server " + cloudAdminServer, True)
        # porgs = yaml.safe_load(porgs)
        # for eachPORG in porgs["results"]:
        #    dir3 = DATA_DIR + "/" + mgmtSubsystemName + "/resources/orgs"
        #    for eachResource3 in apic_resources3:
        #        validateData(dir3, eachResource3, apic_resources3[eachResource3], " --org " + eachPORG["name"], eachPORG["name"], providerOrgServer)





def validateData(parent_dir, resourceTypeName, resourceTypeValue, params, appendDirectory, server):
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
        #runCommand("apic " + resourceTypeName + ":list --fields " + fields + " --server " + cloudAdminServer + " --output " + rdir + " " + list_params, True)
        resourceInstances = runCommand("apic " + resourceTypeName + ":list --format yaml" + " --server " + server + " " + list_params, True)
        resourceInstances = yaml.safe_load(resourceInstances)
        if resourceInstances["total_results"] > 0:
            print ("Creating directory : " + rdir)
            os.makedirs(rdir, mode=0o755, exist_ok=True)
        for eachResourceInstance in resourceInstances["results"]:
            # compare abd validate data
            compareResource(eachResourceInstance, resourceTypeName, rdir)
            
            for eachSubResource in resourceTypeValue:
                if eachSubResource != "field_name" and eachSubResource != "methods" and eachSubResource != "additional_params_for_get" and eachSubResource != "additional_params_for_list" and eachSubResource != "fields_in_list_output":
                    addtionalDir = None
                    #if eachSubResource == "gateway-extensions" or eachSubResource == "catalog-settings":
                    addtionalDir = eachResourceInstance["name"]
                    validateData(rdir, eachSubResource, resourceTypeValue[eachSubResource], params + " --" + resourceTypeValue["field_name"] + " " + eachResourceInstance["name"], addtionalDir, server)
    else:
        print ("custom method, Creating directory : " + rdir)
        os.makedirs(rdir, mode=0o755, exist_ok=True)
        for eachMethod in methods:
            output = None
            if eachMethod == "get":
                output = runCommand("apic " + resourceTypeName + ":" + eachMethod + " --format yaml --server " + server + " " + get_params, False, 1, exitOnError)
                output = yaml.safe_load(output)
                # compareResource(output, resourceTypeName, rdir)
            elif eachMethod in ["list", "list-all"]:
                output = runCommand("apic " + resourceTypeName + ":" + eachMethod + " --format yaml --server " + server + " " + list_params, True, 1, exitOnError)
                output = yaml.safe_load(output)
                for eachResourceInstance in output["results"]:
                    compareResource(eachResourceInstance, resourceTypeName, rdir)

def getManagementSubsystemNameFromSource():
    global mgmtSubsystemName
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
        mgmtSubsystemName = selectedSubsystem
    
    print ("selected management subsystem from the source configuration : ", mgmtSubsystemName)


def compareResource(targetResourceInstance, resourceTypeName, rdir):
    if "name" in targetResourceInstance:
        targetResourceName = targetResourceInstance["name"]
        oldResourceName = targetResourceName
        if resourceTypeName in ["portal-services", "gateway-services"] and targetResourceName.endswith("new"):
            oldResourceName = targetResourceName[:-3] # remove "new" from name
        if resourceTypeName == "analytics-services":
            return # for analytics, target service is not created.
        
        if os.path.exists(rdir + "/" + oldResourceName + ".yaml"):
            text_file = open(rdir + "/" + oldResourceName + ".yaml", "r")
            sourceResourceInstance = text_file.read()
            sourceResourceInstance = yaml.safe_load(sourceResourceInstance)
            text_file.close()
            print ("target resource name : {}, old resource name : {} and old resource file path : {}".format(targetResourceName, oldResourceName, rdir + "/" + oldResourceName + ".yaml"))
            # compare all other fields here
        else:
            # the source resource instance must exist. if not fail.
            if resourceTypeName == "user-registries" or targetResourceName == "common-services":
                print ("WARNING : Assuming target is CP4I and source is NOT CP4I. Source resource instance NOT found for target resource instance with name, {} and resource type, {}, old resource file, {}".format(targetResourceName, resourceTypeName, rdir + "/" + oldResourceName + ".yaml"))
            elif  resourceTypeName == "users":
                print("WARNING : Assuming target is CP4I and source is NOT CP4I. Source resource instance NOT found for target resource instance with name, {} and resource type, {}, old resource file, {}".format(targetResourceName, resourceTypeName, rdir + "/" + oldResourceName + ".yaml"))
            else:
                sys.exit("ERROR : Source resource instance NOT found for target resource instance with name, {} and resource type, {}, old resource file, {}".format(targetResourceName, resourceTypeName, rdir + "/" + oldResourceName + ".yaml"))


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


# start
def start():
    global cloudAdminServer
    print ("CHECKING IF KUBECTL/OC EXIST IN THE PATH AND HAVE ACCESS TO THE CLUSTER :")
    runKubernetesCommand("version", "default")
    
    if args.skip_namespace_validation == False:
        validateNamespaces([args.mgmt_ns, args.ptl_ns, args.gw_ns, args.a7s_ns])
    
    if args.mgmt_ns != None and "|" in args.mgmt_ns:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Invalid namespace({}) provided for management subsystem. Only one namespace need to be provided. Exiting...".format(args.mgmt_ns))

    checkSubsystemHealth()
    getManagementSubsystemNameFromSource()
    print ()
    
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
    if args.check_portal_site_health:
        checkStatusOfPortalSites()
    else:
        print("ACTION OUTPUT : Skipping portal site health check. To check health of portal sites use flag -check_portal_site_health")
        
    print()
    getWebhookStatus()

    validateWithSourceSystemExportedData()
    
    print()
    print()
    print("This script performed the following actions in target APIC system:")
    print("******************************************************************")
    print("1. Checked the health of all the subsystems in the target APIC system.")
    print("2. Checked the status of portal sites.")
    print("3. Checked the status of webhooks and displays a report.")
    print()
    print("Next steps::")
    print("********************************************")
    print("1. If oidc/sso authentication is being used, the redirect URLS have to be updated in the authorization server after migration (for example : Google oidc, need to add the new redirect urls in Google Developer Console). The new redirect URLs can be found in the user registry in cloud manager.")
    print("2. If analytics service present on target system it must be manually associated with the gateways as needed from the Cloud Manager UI.")
    print("3. If target system is CP4I, to login to Platform Navigator you need to use the password from the target APIC system.")
    print("4. The migrated portal and gateway services will have new names (new appended to the old names). Any scripts and utilities written using apic toolkit need to be updated if they are using names as input parameter and not the ids. This is applicable to only portal and gateway names.")
    print("5. Validate the data in the target APIC system by logging into cloud manager and api manager UIs.")
    print("6. Validate the APIs published in the gateways.")
    print("7. Validate the portal site URLs.")
    print("8. Once all the APIs are verified, you may need to update the DNS mapping info to redirect the calls to the new gatways and portals.")



	
parser = argparse.ArgumentParser(description="The script is used to check the health of the target APIC system after the migration. \n\
It check if each subsystem is in running state or not and also the state of the webhooks. \n\n\
Prerequisites ::\n\
1. Access to the APIC cluster (target system) using kubectl or oc.\n\
2. Python 3.x and PyYAML module need to be installed.\n\
3. Right version of apic toolkit must be in the path to run apic commands.\n\
4. Health check is performed on the subsystems.",
formatter_class=argparse.RawDescriptionHelpFormatter)


parser.add_argument("-n", "--namespace", dest = "ns", help="uses this namespace value for all subsystems if individual subsystem namespace is not provided.")
parser.add_argument("-mgmt_ns", "--management_namespace", dest = "mgmt_ns", help="namespace of the management subsystem. This has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-ptl_ns", "-portal_namespace", dest = "ptl_ns", help="namespace of the portal subsystem. This has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-gw_ns", "--gateway_namespace", dest = "gw_ns", help="namespace of the gateway subsystem. This has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-a7s_ns", "--analytics_namespace", dest = "a7s_ns", help="namespace of the analytics subsystem. This has more precedence than the common flag, -n or --namespace.")

parser.add_argument("-mgmt_subsystem_name", "--mgmt_subsystem_name", dest = "mgmt_subsystem_name", help="management subsystem name if multiple management subsystems in the config.")
parser.add_argument('-skip_namespace_validation', "--skip_namespace_validation",  action='store_true', dest = "skip_namespace_validation", help='Skips validation of input namespaces.')

parser.add_argument("-u", "--username", dest = "username", help="username to login to the cloud manager UI.")
parser.add_argument("-p", "--password", dest = "password", help="password to login to the cloud manager UI.")
parser.add_argument("-s", "--server", dest = "server", help="hostname to connect to cloud manager. Use platform api hostname.")
parser.add_argument("-r", "--realm", dest = "realm", help="name of the realm the user belongs to.")
parser.add_argument("-sso", "--sso", dest = "sso", action='store_true', help="Authentication using sso/oidc.")
parser.add_argument("-api_key", "--api_key", dest = "api_key", help="api key used in sso authentication for cloud manager.")

parser.add_argument('-check_portal_site_health', "--check_portal_site_health", action='store_true', dest = "check_portal_site_health", help='Checks health of portal sites when this flag is used.')
parser.add_argument('-silent', "--silent", action='store_true', dest = "silent", help='Does not prompt for additinal inputs and proceeds silently.')

args = parser.parse_args()

print ("Start time :", time.asctime())
print ()
    
print ("Input namespace provided for all subsystems (-n or --namespace flag) : ", args.ns)
print ("Input namespace provided for management subsystem (-mgmt_ns or --management_namespace flag) : ", args.mgmt_ns)
print ("Input namespace provided for portal subsystem (-ptl_ns or --portal_namespace flag) : ", args.ptl_ns)
print ("Input namespace provided for gateway subsystem (-gw_ns or --gateway_namespace flag) : ", args.gw_ns)
print ("Input namespace provided for analytics subsystem (-a7s_ns or --analytics_namespace flag) : ", args.a7s_ns)
print ()

print ("Host name to connect to cloud manager(-s or --server flag) : ", args.server)
print ("Realm to which user belongs (-r or --realm flag) : ", args.realm)
print ("Cloud manager UI username (-u or --username flag) : ", args.username)
print ("Cloud manager UI password (-p or --password flag) : ********")#password obfuscated
print ("SSO flag (-sso or --sso flag) : ", args.sso)
print ("api key (-api_key or --api_key flag) : ", args.api_key)
print ()

print ("Checks portal site health (-check_portal_site_health or --check_portal_site_health flag) : ", args.check_portal_site_health)
print ("silent (-silent or --silent flag) : ", args.silent)
print ()

forceLogPasswords = os.getenv("FORCE_LOG_PASSWORDS")

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

print()
print()
if args.mgmt_ns == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Exiting. Management namespace not provided. Given value for management namespace is {}. ".format(args.mgmt_ns))
    
if args.gw_ns == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Exiting. Gateway namespace not provided. Given value for gateway namespace is {}. ".format(args.gw_ns))

if args.server == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Server(-s or --server flag) value are needed to check the webhook status using apic toolkit. Exiting...")
    
if args.sso == False and (args.realm == None or args.username == None or args.password == None):
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : SSO flag is false. Its username/password based authentication. Realm(-r or --realm flag) , Username(-u or --username flag) and password(-p or --password flag) are needed to check webhook status using apic toolkit. Exiting...")


print ()
print ("Namespace used for management subsystem : ", args.mgmt_ns)
print ("Namespace used for portal subsystem : ", args.ptl_ns)
print ("Namespace used for gateway subsystem : ", args.gw_ns)
print ("Namespace used for analytics subsystem : ", args.a7s_ns)
print ()

ns.append(args.mgmt_ns)
ns.append(args.ptl_ns)
ns.append(args.gw_ns)
ns.append(args.a7s_ns)

pwd = os.getcwd()
DATA_DIR = pwd + "/data"
DATA_TEMP_DIR = pwd + "/data/temp"

# load config data if exists
if os.path.exists(DATA_DIR + "/" + CONFIG_FILE_NAME):
    print ("Source APIC system configuration file exists. Loading it")
    text_file = open(DATA_DIR + "/" + CONFIG_FILE_NAME, "r")
    config1 = text_file.read()
    print("management configuration : ", config1)
    config = yaml.safe_load(config1)
    text_file.close()
else:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : config.yaml file with details of the source APIC system in NOT present in the data directory. Exiting...")

start()

print ()
print ("End time :", time.asctime())