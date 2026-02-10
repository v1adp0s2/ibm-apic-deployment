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
from urllib.parse import urlparse

oc_client = "oc"
kubectl_client = "kubectl"
client = oc_client

pwd = None
DATA_DIR = None
DATA_TEMP_DIR = None
CONFIG_FILE_NAME = "config.yaml"
cloudAdminServer = None
forceLogPasswords = None

config =  None
targetSystemSpecVersion = None
targetSystemReconciledVersion = None

GATEWAY_PORTAL_MAPPING_FILENAME = "gateway_portal_mapping.yaml"
gateway_portal_mapping = None

created = 0
selectedSubsystem = None

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


def getGatewayOrPortalServices(serviceName):
    if serviceName != "gateway" and serviceName != "portal":
        print ("Time when error occurred :", time.asctime())
        sys.exit("Invalid service name provided. Valid values are gateway or portal.")
    
    fields = "name,endpoint,url"
    if serviceName == "gateway":
        fields = fields + ",api_endpoint_base"
    else:
        fields = fields + ",web_endpoint_base"

    output = {}
    orgs = runCommand("apic orgs:list --org_type=admin --fields id,name --server " + cloudAdminServer, True)
    orgs = yaml.safe_load(orgs)
    for org in orgs["results"]:
        azones = runCommand("apic availability-zones:list --fields id,name --server " + cloudAdminServer + " --org " + org["name"], True)
        azones = yaml.safe_load(azones)
        for azone in azones["results"]:
            services = runCommand("apic " + serviceName + "-services:list --fields " + fields + " --server " + cloudAdminServer + " --org " + org["name"] + " --availability-zone " + azone["name"], True)
            services = yaml.safe_load(services)
            for service in services["results"]:
                if serviceName == "gateway":
                    output[service["endpoint"]] = service["name"] + "|" + service["api_endpoint_base"] + "|" + service["url"]
                else:
                    output[service["endpoint"]] = service["name"] + "|" + service["web_endpoint_base"] + "|" + service["url"]
    return output


def registerGatewayServices():
    global created
    global selectedSubsystem
    print ("Register new gateway services::::")
    #get the saved configuration
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
    
    
    if selectedSubsystem == None:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : No configuration found for the management subsystem from the source system.  Exiting...")
    else:
        print()
        print ("selected management subsystem from the source configuration : ", selectedSubsystem)
        print()
        managementSubsystemDetails = config["management_subsystem"][selectedSubsystem]
        
        resetGatewayPortal = False
        if resetGatewayPortal:
            resetGateways()
            resetPortals()
            print()
            print("ACTION OUTPUT : Exiting as reset_gateway_portal is set.")
            print("ACTION OUTPUT : Start from restore management database step and complete migration.")
            print()
            print ("End time :", time.asctime())
            sys.exit(0)
        
        sourceSystemReconciledVersion = managementSubsystemDetails["versionReconciled"]
        print ("Source system version : {} and target system version : {}".format(sourceSystemReconciledVersion, targetSystemReconciledVersion))
        print()
        if args.ignore_version_check == False and targetSystemReconciledVersion != None and sourceSystemReconciledVersion.startswith("2018.") == False:
            if sourceSystemReconciledVersion.index("-") > 0:
                version1 = sourceSystemReconciledVersion[0:sourceSystemReconciledVersion.index("-")]
                if targetSystemReconciledVersion.startswith(version1) == False:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Target system version({}) does not match the soure system version({}).  Exiting...".format(targetSystemReconciledVersion, sourceSystemReconciledVersion))
    
    
        if not args.skip_gw:
            if "registered_gateways" not in managementSubsystemDetails:
                print ("ACTION OUTPUT : No gateways are registered in the management subsystem of the source system. Exiting...")
                print ("Current time :", time.asctime())
                sys.exit(1)
                 
            gatewaysFromSouceSystem = managementSubsystemDetails["registered_gateways"]
            if len(gatewaysFromSouceSystem) > 0:
                print ("********************************************************************************************************************")
                print ("********************************************************************************************************************")
                print ("FOR EACH GATEWAY FROM THE SOURCE SYSTEM, ENTER THE CORROSPONDING NEW GATEWAY ENDPOINTS FROM THE TARGET APIC SYSTEM :")
                print()
                print ("If there is no corrosponding gateway in target apic system OR if you need to keep the same gateway from source system even in the target apic system as well, skip it by pressing enter key.")
            else:
                print ("ACTION OUTPUT : No gateway configuration found in the saved source APIC system configuration")


            count = 1
            for eachGWName in gatewaysFromSouceSystem:
                eachGW = gatewaysFromSouceSystem[eachGWName]
                
                gatewayType = None
                if eachGW["gateway_service_type"] == "datapower-gateway":
                    gatewayType = "DataPower Gateway (v5 compatible)"
                elif eachGW["gateway_service_type"] == "datapower-api-gateway":
                    gatewayType = "DataPower API Gateway"

                print()
                print(str(count) + ". source gateway title : ", eachGW["title"])
                print("    gateway type : " + gatewayType)
                print("    endpoint : ", eachGW["endpoint"])
                print("    api_endpoint_base : ", eachGW["api_endpoint_base"])
                
                orgId = eachGW["org_url"][eachGW["org_url"].rindex("/")+1:]
                azoneId = eachGW["availability_zone_url"][eachGW["availability_zone_url"].rindex("/")+1:]
                
                new_endpoint = None
                new_apiendpoint_base = None
                sourceCommunicationKind = None
                targetCommunicationKind = None
                if "communication_kind" in eachGW:
                    sourceCommunicationKind = eachGW["communication_kind"]
                if args.silent:
                    if "gateway_mapping" in gateway_portal_mapping and eachGW["name"] in gateway_portal_mapping["gateway_mapping"]:
                        gwInfo = gateway_portal_mapping["gateway_mapping"][eachGW["name"]]
                        new_endpoint = gwInfo[eachGW["endpoint"]]
                        new_apiendpoint_base = gwInfo[eachGW["api_endpoint_base"]]
                        if sourceCommunicationKind != None and sourceCommunicationKind in gwInfo:
                            targetCommunicationKind = gwInfo[sourceCommunicationKind]
                else:
                    new_endpoint = input("ENTER THE NEW GATEWAY ENDPOINT aka gateway manager/director(corresponding to the old gw endpoint) FROM THE TARGET APIC SYSTEM, (must start with https)     : ")
                    new_apiendpoint_base = input("ENTER THE NEW GATEWAY API_ENDPOINT_BASE aka gateway(corresponding to the old gw value) FROM THE TARGET APIC SYSTEM, (must start with https)     : ")
                    targetCommunicationKind = input("ENTER communication kind (external or internal_svc) for this gateway     : ")
                
                if new_endpoint != None: new_endpoint = new_endpoint.strip()
                if new_apiendpoint_base != None: new_apiendpoint_base = new_apiendpoint_base.strip()
                if targetCommunicationKind != None: targetCommunicationKind = targetCommunicationKind.strip()
                
                print()
                count = count + 1
                if new_endpoint != None and len(new_endpoint) > 0 and new_endpoint != "https://NEW_GATEWAY_ENDPOINT_HOST_IN_TARGET_SYSTEM":

                    if new_endpoint != None and len(new_endpoint) > 0 and new_endpoint.startswith("https://") == False:
                        print("ACTION OUTPUT : " + new_endpoint + " for gateway NOT starting with https:// so add https:// explicitely.")
                        new_endpoint = "https://" + new_endpoint

                    if new_apiendpoint_base != None and len(new_apiendpoint_base) > 0 and new_apiendpoint_base.startswith("https://") == False:
                        print(new_apiendpoint_base + " for gateway NOT starting with https:// so add https:// explicitely.")
                        new_apiendpoint_base = "https://" + new_apiendpoint_base
                    
                    if new_endpoint.endswith("/"):
                        new_endpoint =  new_endpoint[:-1]
                    
                    if new_apiendpoint_base.endswith("/"):
                        new_apiendpoint_base =  new_apiendpoint_base[:-1]
                    
                    if targetCommunicationKind != None and targetCommunicationKind != "external" and targetCommunicationKind != "internal_svc":
                        sys.exit("Invalid communication kind({}) provided while registering gateway. Exiting...".format(targetCommunicationKind))
                    
                    print ("NEW GATEWAY ENDPOINT aka gateway manager/director(corresponding to the old gw endpoint) FROM THE TARGET APIC SYSTEM : ", new_endpoint)
                    print ("NEW GATEWAY API_ENDPOINT_BASE aka gateway(corresponding to the old gw value) FROM THE TARGET APIC SYSTEM : ", new_apiendpoint_base)
                    print ("NEW GATEWAY communication kind FROM THE TARGET APIC SYSTEM : ", targetCommunicationKind)

                    if os.path.exists(DATA_TEMP_DIR + "/" + eachGW["name"] + ".yaml"):
                        os.remove(DATA_TEMP_DIR + "/" + eachGW["name"] + ".yaml")
                    #get
                    oldGW = runCommand("apic gateway-services:get --server " + cloudAdminServer + " --org " + orgId + " --availability-zone " + azoneId + " " + eachGW["id"] + " --output " + DATA_TEMP_DIR, True, 1, False)
                    if oldGW.startswith("Error: Resource not found"):
                        print("ACTION OUTPUT : Gateway({}) from source system NOT found in target system management database. Looks like this gateway is already migrated or not found in target. Skipping it.".format(eachGW["name"]))
                        continue

                    if oldGW != None and len(oldGW) > 0:
                        oldGW = oldGW.split()
                        print ("reponse file ::: ", oldGW[1])
                        if os.path.exists(oldGW[1]):
                            text_file = open(oldGW[1], "r")
                            oldGWRecord = text_file.read()
                            text_file.close()
                            oldGWRecord = yaml.safe_load(oldGWRecord)
                            oldGWId = oldGWRecord["id"]
                            oldGWName = oldGWRecord["name"]
                            if "type" in oldGWRecord: del oldGWRecord["type"]
                            if "api_version" in oldGWRecord: del oldGWRecord["api_version"]
                            if "id" in oldGWRecord: del oldGWRecord["id"]
                            if "oauth_shared_secret" in oldGWRecord and oldGWRecord["oauth_shared_secret"].startswith("***"):
                                del oldGWRecord["oauth_shared_secret"]
                            if "owned" in oldGWRecord: del oldGWRecord["owned"]
                            if "configuration" in oldGWRecord: del oldGWRecord["configuration"]
                            if "state" in oldGWRecord: del oldGWRecord["state"]
                            if "service_supported_features" in oldGWRecord: del oldGWRecord["service_supported_features"]
                            if "webhook_url" in oldGWRecord: del oldGWRecord["webhook_url"]
                            if "availability_zone_url" in oldGWRecord: del oldGWRecord["availability_zone_url"]
                            #delete old analytics reference as we are not migrating analytics
                            if "analytics_service_url" in oldGWRecord: del oldGWRecord["analytics_service_url"]
                            if "service_version" in oldGWRecord: del oldGWRecord["service_version"]
                            if "communication_to_analytics_kind" in oldGWRecord: del oldGWRecord["communication_to_analytics_kind"]
                            if "communication_to_analytics_with_jwt" in oldGWRecord: del oldGWRecord["communication_to_analytics_with_jwt"]
                            if "created_at" in oldGWRecord: del oldGWRecord["created_at"]
                            if "updated_at" in oldGWRecord: del oldGWRecord["updated_at"]
                            if "url" in oldGWRecord: del oldGWRecord["url"]
                            if "org_url" in oldGWRecord: del oldGWRecord["org_url"]
                            oldGWRecord["title"] = oldGWRecord["title"] + "new"
                            oldGWRecord["name"] = oldGWRecord["name"] + "new"
                            oldGWRecord["endpoint"] = new_endpoint
                            oldGWRecord["api_endpoint_base"] = new_apiendpoint_base
                            if targetCommunicationKind != None:
                                oldGWRecord["communication_kind"] = targetCommunicationKind
                            
                            # check if exists and create if needed
                            print ("Fetching existing gateway services/endpoints and checking if the endpoint({}) already exsits or not.".format(oldGWRecord["endpoint"]))
                            gwData = getGatewayOrPortalServices("gateway")
                            if oldGWRecord["endpoint"] not in gwData:
                                newgwFileName = DATA_TEMP_DIR + "/" + oldGWRecord["name"] + ".yaml"
                                with open(newgwFileName, 'w') as newGWServiceFile:
                                    yaml.dump(oldGWRecord, newGWServiceFile,  default_flow_style=False)
                                #create new gateway service
                                newGateway = runCommand("apic gateway-services:create --server " + cloudAdminServer + " --org " + orgId + " --availability-zone " + azoneId + " " + newgwFileName)
                                print ("ACTION OUTPUT : New gateway created, name and url values : {}".format(newGateway))
                                newGateway = newGateway.strip()
                                newGatewayId = newGateway[newGateway.rindex("/") + 1:]
                                created = 1
                                
                                eachGW["NEW_ENDPOINT"] = oldGWRecord["endpoint"]
                                eachGW["NEW_API_ENDPOINT_BASE"] = oldGWRecord["api_endpoint_base"]
                                eachGW["NEW_NAME"] = oldGWRecord["name"]
                                eachGW["NEW_URL"] = newGateway[newGateway.index("https://"):]
                                #save config file
                                with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
                                    yaml.dump(config, configFile,  default_flow_style=False)
                            else:
                                print ("ACTION OUTPUT : GATEWAY SERVICE WITH ENDPOINT({}) ALREADY EXISTS IN THE DATABASE.".format(oldGWRecord["endpoint"]))
                                created = 2
                                val = gwData[oldGWRecord["endpoint"]].split("|")
                                newGatewayId =  val[0].strip() # name
                                eachGW["NEW_ENDPOINT"] = oldGWRecord["endpoint"]
                                eachGW["NEW_API_ENDPOINT_BASE"] = val[1]
                                eachGW["NEW_NAME"] = val[0].strip()
                                eachGW["NEW_URL"] = val[2]
                                #save config file
                                with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
                                    yaml.dump(config, configFile,  default_flow_style=False)
                                print("")
                            
                            #check for global extensions in old gateway and if it exists create in new gateway
                            #no list command, do a get and check for error message "Error: Resource not found"
                            if os.path.exists(DATA_TEMP_DIR + "/gateway-extension.yaml"):
                                os.remove(DATA_TEMP_DIR + "/gateway-extension.yaml")
                            oldGatewayExtension = runCommand("apic gateway-extensions:get --scope org --server " + cloudAdminServer + " --org " + orgId + " --availability-zone " + azoneId + " --gateway-service " + oldGWId + " --output " + DATA_TEMP_DIR, True, 1, False)
                            if "Error" not in oldGatewayExtension:
                                print ("ACTION OUTPUT : Found gateway extension in old gateway : " + oldGatewayExtension)
                                if os.path.exists(DATA_TEMP_DIR + "/gateway-extension.yaml"):
                                    os.remove(DATA_TEMP_DIR + "/gateway-extension.yaml")
                                newGatewayExtension = runCommand("apic gateway-extensions:get" + " --output " + DATA_TEMP_DIR + " --scope org --server " + cloudAdminServer + " --org " + orgId + " --availability-zone " + azoneId + " --gateway-service " + newGatewayId, True, 1, False)
                                if "Error" in newGatewayExtension:
                                    print ("ACTION OUTPUT : No gateway extension found in new gateway, creating it")
                                    if os.path.exists(DATA_TEMP_DIR + "/gateway_extension_implementation.zip"):
                                        os.remove(DATA_TEMP_DIR + "/gateway_extension_implementation.zip")
                                    out1 = runCommand("apic gateway-extensions:implementation --server " + cloudAdminServer + " --org " + orgId + " --availability-zone " + azoneId + " --gateway-service " + oldGWId + " --output " + DATA_TEMP_DIR )
                                    out1 = out1.strip()
                                    extensionZipPath = out1[out1.rindex(" ") + 1:]
                                    #extensionZipPath = "/Users/sambadas5/Downloads/POLICY_EXTENSION/downloaded/Example-Manifest-Extension.zip"
                                    gatewayExtension = runCommand("apic gateway-extensions:create " + extensionZipPath + " --scope org --server " + cloudAdminServer + " --org " + orgId + " --availability-zone " + azoneId + " --gateway-service " + newGatewayId)
                                    print ("ACTION OUTPUT : Created new gateway extension with details for gateway, {} and gateway extension details : {} ".format(oldGWRecord["name"], gatewayExtension))
                                else:
                                    print ("ACTION OUTPUT : Found gateway extension in new gateway : " + newGatewayExtension)
                            else:
                                print ("ACTION OUTPUT : No gateway extensions found in the old gateway service, name : {} and id : {} ".format(oldGWName, oldGWId))
                                
                        else:
                            print ("Time when error occurred :", time.asctime())
                            sys.exit("ERROR : Could not find the yaml file for gateway_service, file name : {}, org : {}, availability_zone : {}, gateway service id : {}. Exiting...".format(oldGW[1], orgId, azoneId, eachGW["id"]))
                    else:
                        print ("Time when error occurred :", time.asctime())
                        sys.exit("ERROR : Get gateway_service, call FAILED : org : {}, availability_zone : {}, gateway service id : {}. Exiting...".format(orgId, azoneId, eachGW["id"]))
                else:
                    print("ACTION OUTPUT : As new gateway endpoint details are not given, skipping old gateway with name : {}, endpoint : {} and api_endpoint_base : {}".format(eachGW["name"], eachGW["endpoint"], eachGW["api_endpoint_base"]))
        else:
            print ("ACTION OUTPUT : Skipping gateway service registration as -skip_gw or --skip_gateway is set")

              
def registerPortalServices():
    global created
    print("\n\n")
    print ("Register new portal services::::")

    if selectedSubsystem == None:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : No configuration found for the management subsystem from the source system.  Exiting...")
    else:
        print()
        print ("selected management subsystem from the source configuration : ", selectedSubsystem)
        print()
        managementSubsystemDetails = config["management_subsystem"][selectedSubsystem]
        if not args.skip_ptl:
            if "registered_portals" not in managementSubsystemDetails:
                print ("ACTION OUTPUT : No portals are registered in the management subsystem of the source system. Exiting...")
                print ("Current time :", time.asctime())
                sys.exit(1)
                 
            portalsFromSouceSystem = managementSubsystemDetails["registered_portals"]
            if len(portalsFromSouceSystem) > 0:
                print ("******************************************************************************************************************")
                print ("FOR EACH PORTAL FROM THE SOURCE SYSTEM, ENTER THE CORROSPONDING NEW PORTAL ENDPOINTS FROM THE TARGET APIC SYSTEM :")
                print()
                print ("If there is no corrosponding portal in target apic system OR if you need to keep the same portal from source system even in the target apic system as well, that can be skipped by pressing enter key.")
            else:
                print ("ACTION OUTPUT : No portal configuration found in the saved source APIC system configuration")

            print()
            count = 1
            for eachPortalName in portalsFromSouceSystem:
                eachPortal = portalsFromSouceSystem[eachPortalName]
                print(str(count) + ". title : ", eachPortal["title"])
                print("endpoint : ", eachPortal["endpoint"])
                print("web_endpoint_base : ", eachPortal["web_endpoint_base"])
                orgId = eachPortal["org_url"][eachPortal["org_url"].rindex("/")+1:]
                azoneId = eachPortal["availability_zone_url"][eachPortal["availability_zone_url"].rindex("/")+1:]
                
                new_endpoint = None
                new_web_endpoint_base = None
                sourceCommunicationKind = None
                targetCommunicationKind = None
                if "communication_kind" in eachPortal:
                    sourceCommunicationKind = eachPortal["communication_kind"]
                if args.silent:
                    if "portal_mapping" in gateway_portal_mapping and eachPortal["name"] in gateway_portal_mapping["portal_mapping"]:
                        portalInfo = gateway_portal_mapping["portal_mapping"][eachPortal["name"]]
                        new_endpoint = portalInfo[eachPortal["endpoint"]]
                        new_web_endpoint_base = portalInfo[eachPortal["web_endpoint_base"]]
                        if sourceCommunicationKind != None and sourceCommunicationKind in portalInfo:
                            targetCommunicationKind = portalInfo[sourceCommunicationKind]
                else:
                    new_endpoint = input("ENTER THE NEW PORTAL ENDPOINT aka portal director(corresponding to the old portal endpoint) FROM THE TARGET APIC SYSTEM, (must start with https)     : ")
                    new_web_endpoint_base = input("ENTER THE NEW PORTAL WEB_ENDPOINT_BASE aka portal web(corresponding to the old portal value) FROM THE TARGET APIC SYSTEM, (must start with https)     : ")
                    targetCommunicationKind = input("ENTER communication kind (external or internal_svc) for this portal     : ")
                
                
                if new_endpoint != None: new_endpoint = new_endpoint.strip()                
                if new_web_endpoint_base != None: new_web_endpoint_base = new_web_endpoint_base.strip()
                if targetCommunicationKind != None: targetCommunicationKind = targetCommunicationKind.strip()
                
                print()
                count = count + 1
                if new_endpoint != None and len(new_endpoint) > 0 and new_endpoint != "https://NEW_PORTAL_ENDPOINT_HOST_IN_TARGET_SYSTEM":

                    if new_endpoint != None and len(new_endpoint) > 0 and new_endpoint.startswith("https://") == False:
                        print("ACTION OUTPUT : " + new_endpoint + " for portal NOT starting with https:// so add https:// explicitely.")
                        new_endpoint = "https://" + new_endpoint

                    if new_web_endpoint_base != None and len(new_web_endpoint_base) > 0 and new_web_endpoint_base.startswith("https://") == False:
                        print(new_web_endpoint_base + " for portal NOT starting with https:// so add https:// explicitely.")
                        new_web_endpoint_base = "https://" + new_web_endpoint_base
                    
                    if new_endpoint.endswith("/"):
                        new_endpoint =  new_endpoint[:-1]
                    
                    if new_web_endpoint_base.endswith("/"):
                        new_web_endpoint_base =  new_web_endpoint_base[:-1]

                    if targetCommunicationKind != None and targetCommunicationKind != "external" and targetCommunicationKind != "internal_svc":
                        sys.exit("Invalid communication kind({}) provided while registering portal. Exiting...".format(targetCommunicationKind))
                    
                    print("NEW PORTAL ENDPOINT aka portal director(corresponding to the old portal endpoint) FROM THE TARGET APIC SYSTEM : ", new_endpoint)
                    print("NEW PORTAL WEB_ENDPOINT_BASE aka portal web(corresponding to the old portal value) FROM THE TARGET APIC SYSTEM : ", new_web_endpoint_base)
                    print ("NEW PORTAL communication kind FROM THE TARGET APIC SYSTEM : ", targetCommunicationKind)

                    if os.path.exists(DATA_TEMP_DIR + "/" + eachPortal["name"] + ".yaml"):
                        os.remove(DATA_TEMP_DIR + "/" + eachPortal["name"] + ".yaml")
                    #get
                    oldPortal = runCommand("apic portal-services:get --server " + cloudAdminServer  + " --output " + DATA_TEMP_DIR + " --org " + orgId + " --availability-zone " + azoneId + " " + eachPortal["id"], True, 1, False)
                    if oldPortal.startswith("Error: Resource not found"):
                        print("ACTION OUTPUT : Portal({}) from source system NOT found in target system management database. Looks like this portal is already migrated or not found in target. Skipping it.".format(eachPortal["name"]))
                        continue

                    if oldPortal != None and len(oldPortal) > 0:
                        oldPortal = oldPortal.split()
                        print ("reponse file ::: ", oldPortal[1])
                        if os.path.exists(oldPortal[1]):
                            text_file = open(oldPortal[1], "r")
                            oldPortalRecord = text_file.read()
                            text_file.close()
                            oldPortalRecord = yaml.safe_load(oldPortalRecord)
                            if "type" in oldPortalRecord: del oldPortalRecord["type"]
                            if "api_version" in oldPortalRecord: del oldPortalRecord["api_version"]
                            if "id" in oldPortalRecord: del oldPortalRecord["id"]
                            if "owned" in oldPortalRecord: del oldPortalRecord["owned"]
                            if "webhook_url" in oldPortalRecord: del oldPortalRecord["webhook_url"]
                            if "service_supported_features" in oldPortalRecord: del oldPortalRecord["service_supported_features"]
                            if "state" in oldPortalRecord: del oldPortalRecord["state"]
                            if "availability_zone_url" in oldPortalRecord: del oldPortalRecord["availability_zone_url"]
                            if "service_version" in oldPortalRecord: del oldPortalRecord["service_version"]
                            if "created_at" in oldPortalRecord: del oldPortalRecord["created_at"]
                            if "updated_at" in oldPortalRecord: del oldPortalRecord["updated_at"]
                            if "url" in oldPortalRecord: del oldPortalRecord["url"]
                            if "org_url" in oldPortalRecord: del oldPortalRecord["org_url"]
                            oldPortalRecord["title"] = oldPortalRecord["title"] + "new"
                            oldPortalRecord["name"] = oldPortalRecord["name"] + "new"
                            oldPortalRecord["endpoint"] = new_endpoint
                            oldPortalRecord["web_endpoint_base"] = new_web_endpoint_base
                            if targetCommunicationKind != None:
                                oldPortalRecord["communication_kind"] = targetCommunicationKind
                            
                            # check if exists ann create if needed
                            print ("Fetching existing portal services/endpoints and checking if the endpoint({}) already exsits or not.".format(oldPortalRecord["endpoint"]))
                            ptlData = getGatewayOrPortalServices("portal")
                            print(ptlData)
                            if oldPortalRecord["endpoint"] not in ptlData:
                                pFileName = DATA_TEMP_DIR + "/" + oldPortalRecord["name"] + ".yaml"
                                with open(pFileName, 'w') as newPortalServiceFile:
                                    yaml.dump(oldPortalRecord, newPortalServiceFile,  default_flow_style=False)
                                #create new portal service
                                newPortal = runCommand("apic portal-services:create --server " + cloudAdminServer + " --org " + orgId + " --availability-zone " + azoneId + " " + pFileName)
                                newPortal = newPortal.strip()
                                print ("ACTION OUTPUT : New portal created, name and url values : {}".format(newPortal))
                                created = 1
                                eachPortal["NEW_ENDPOINT"] = oldPortalRecord["endpoint"]
                                eachPortal["NEW_WEB_ENDPOINT_BASE"] = oldPortalRecord["web_endpoint_base"]
                                eachPortal["NEW_NAME"] = oldPortalRecord["name"]
                                eachPortal["NEW_URL"] = newPortal[newPortal.index("https://"):]
                                #save config file
                                with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
                                    yaml.dump(config, configFile,  default_flow_style=False)
                            else:
                                print ("ACTION OUTPUT : PORTAL SERVICE WITH ENDPOINT({}) ALREADY EXISTS IN THE DATABASE.".format(oldPortalRecord["endpoint"]))
                                val = ptlData[oldPortalRecord["endpoint"]].split("|")
                                eachPortal["NEW_ENDPOINT"] = oldPortalRecord["endpoint"]
                                eachPortal["NEW_WEB_ENDPOINT_BASE"] = val[1]
                                eachPortal["NEW_NAME"] = val[0].strip()
                                eachPortal["NEW_URL"] = val[2]
                                #save config file
                                with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
                                    yaml.dump(config, configFile,  default_flow_style=False)
                                created = 2
                        else:
                            print ("Time when error occurred :", time.asctime())
                            sys.exit("ERROR : Could not find the yaml file for portal_service, file name : {}, org : {}, availability_zone : {}, portal service id : {}. Exiting...".format(oldPortal[1], orgId, azoneId, eachPortal["id"]))
                    else:
                        print ("Time when error occurred :", time.asctime())
                        sys.exit("ERROR : Get portal_service, call FAILED : org : {}, availability_zone : {}, portal service id : {}. Exiting...".format(orgId, azoneId, eachPortal["id"]))
                else:
                    print("ACTION OUTPUT : As new portal endpoint details are not given, skipping old portal with name : {}, endpoint : {} and web_endpoint_base : {}".format(eachPortal["name"], eachPortal["endpoint"], eachPortal["web_endpoint_base"]))
        else:
            print ("ACTION OUTPUT : Skipping portal service registration as -skip_ptl or --skip_portal is set")           


def resetGateways():
    if args.gw_ns == None or args.gw_ns == "":
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Gateway namespace(s) not provided to reset the gateways. Given value is {}".format(args.gw_ns))

    multipleNS = args.gw_ns.split("|")
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
    print("Waiting for 3 minutes.")
    time.sleep(180)
    print("ACTION OUTPUT : Check if all the gateway pods are healthy before proceeding further.")
    print("\n")



def resetPortals():
    portalServices = getGatewayOrPortalServices("portal")
    print()
    print()
    portalReset = False
    for eachEndpoint in portalServices:
        managementSubsystemDetails = config["management_subsystem"][selectedSubsystem]
        if "registered_portals" in managementSubsystemDetails:
            portalsFromSouceSystem = managementSubsystemDetails["registered_portals"]
            if eachEndpoint in portalsFromSouceSystem: #old portal entry
                continue

        print("Resetting registered portal service with name : ", portalServices[eachEndpoint])
        out = runCommand("apic factory-reset:delete --mode portaladmin --execute_reset true --server " + cloudAdminServer + " --portal_service_name " + portalServices[eachEndpoint], True, 0, False)
        if out != None and out != "" and out.lower().startswith("error") == False:
            portalReset = True
            print ("Portal factory resest output : [[" + out + "]]")
            print()
            time.sleep(30)

        if portalReset:
            print("Waiting for 3 minutes. Current time : ", time.asctime())
            print("ACTION OUTPUT : login to portal admin pod and confirm that all portal sites are deleted(command : list_sites) before proceeding further.")
            time.sleep(180)
        else:
            print("No new registered portals in management subsystem or no data to reset on the portal subsystem for this portal.")
    print("\n")


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


#OCP : update topCRName-mgmt-admin-pass secret with the correct password
#CP4I : delete topCRName-configurator secret
#CP4I : delete configurator job and it will get created again and run.
#this will create common-services user registry.
#the new portal and gateway services are already created using this script
def updateData_OCPAndCP4i():

    if "restartedConfigurator" in config["management_subsystem"][selectedSubsystem] and config["management_subsystem"][selectedSubsystem]["restartedConfigurator"] == True:
        print("ACTION OUTPUT : Not updating topcr-mgmt-admin-pass secret as restartedConfigurator = true in the config file.")
        print("ACTION OUTPUT : Not deleting topcr-configurator secret as restartedConfigurator = true in the config file.")
        print("ACTION OUTPUT : Not deleting topcr-cp4i-creds secret as restartedConfigurator = true in the config file.")
        print("ACTION OUTPUT : Not deleting topcr-configurator JOB as restartedConfigurator = true in the config file.")
        return

    out1 = runKubernetesCommand("get apiconnectcluster.apiconnect.ibm.com --no-headers", args.mgmt_ns, True, 1, False)
    if out1 != None and out1 != "" and out1.lower().startswith("error") == False:
        out1 = out1.strip()
        topCRName = out1[0:out1.index(" ")]
        print("top cr name : ", topCRName)

        #update topCRName-mgmt-admin-pass secret with the actual cloud manager admin password of cloud manager LUR
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
        out3 = runKubernetesCommand("get secret " + adminsecretName + " --no-headers", args.mgmt_ns, True, 1, False)
        if out3 != None and out3 != "" and out3.lower().startswith("error") == False:
            encodedPassword = base64.b64encode(args.password.encode('ascii'))
            encodedPassword = encodedPassword.decode("ascii")
            runKubernetesCommand('patch secret ' + adminsecretName + ' --patch="{\\"data\\":{\\"password\\":\\"'+encodedPassword+'\\"}}"', args.mgmt_ns, False)
            print("ACTION OUTPUT : Updated secret(" + adminsecretName + " with cloud manager password after restoring database. Configurator job will use this password in case of cp4i")
        
        print()
        #delete topCRName-configurator secret
        cp4iSecretName = adminsecretName.removesuffix('-mgmt-admin-pass')
        out2 = runKubernetesCommand("get secret " + cp4iSecretName + "-configurator --no-headers", args.mgmt_ns, True, 0, False)
        if out2 != None and out2 != "" and out2.lower().startswith("error") == False:
            runKubernetesCommand("delete secret " + cp4iSecretName + "-configurator", args.mgmt_ns, False)
            print("ACTION OUTPUT : Deleted secret(" + cp4iSecretName + "-configurator) in CP4I. When configurator job is rerun, it gets created again.")

        if "cp4i_registration_secret" not in config["management_subsystem"][selectedSubsystem]:
            print()
            #delete topCRName-cp4i-creds secret
            out3 = runKubernetesCommand("get secret " + cp4iSecretName + "-cp4i-creds --no-headers", args.mgmt_ns, True, 0, False)
            if out3 != None and out3 != "" and out3.lower().startswith("error") == False:
                runKubernetesCommand("delete secret " + cp4iSecretName + "-cp4i-creds", args.mgmt_ns, False)
                print("ACTION OUTPUT : Deleted secret(" + cp4iSecretName + "-cp4i-creds) in CP4I. When configurator job is rerun, it gets created again.")
        else:
            print("ACTION OUTPUT : Source system is cp4i. NOT deleting the topcr-cp4i-creds secret. Source system secret is already applied after management db is restored.")
    
        print()
        #delete configurator job
        print("Checking if configurator job exists::")
        output = runKubernetesCommand("get job -l app.kubernetes.io/component=configurator", args.mgmt_ns, True)
        if output != None and output != "":
            output = output.splitlines()
            if len(output) >= 2:
                configuratorJobName = output[1][0:output[1].index(" ")]
                print ("Found configurator job with name : " + configuratorJobName)
                runKubernetesCommand("delete job " + configuratorJobName, args.mgmt_ns, False)
                print ("ACTION OUTPUT  :Deleted configurator job with name : " + configuratorJobName)

                flag = True
                loopCount = 0
                apicReady = False
                # topCRName = configuratorJobName[0:configuratorJobName.rindex("-")]
                while flag:
                    loopCount = loopCount + 1
                    if loopCount >= 15:
                        sys.exit ("Timeout after waiting for apic cluster to be ready after configurator job was restarted. Current time : " + time.asctime())

                    if apicReady == False:
                        res1 = runKubernetesCommand("get apiconnectcluster.apiconnect.ibm.com " + topCRName + " -o yaml", args.mgmt_ns, True, 0, False)
                        if res1 != None and res1 != "" and res1.lower().startswith("error") == False:
                            res1 = yaml.safe_load(res1)
                            if "status" in res1 and "conditions" in res1["status"]:
                                conditions = res1["status"]["conditions"]
                                for eachCondition in conditions:
                                    if eachCondition["type"] == "Ready" and eachCondition["status"] == "True":
                                        print("ACTION OUTPUT : APIC is healthy again.")
                                        apicReady = True

                    if apicReady:
                        flag = False
                    else:
                        print ("Waiting for APIC instance to be ready. Current time : ", time.asctime())
                        time.sleep(60)
                config["management_subsystem"][selectedSubsystem]["restartedConfigurator"] = True
                with open(DATA_DIR + "/" + CONFIG_FILE_NAME, 'w') as configFile:
                    yaml.dump(config, configFile, default_flow_style=False)


        else:
            print("ACTION OUTPUT : No configurator job exists.")
    else:
        print ("ACTION OUTPUT :  Top CR NOT found. Not a OCP/CP4I environment.")

# updating the cloud name value using api manager endpoint.
def updateCloudData():
    cloudNameUpdateData = {
        "cloud_name" : "value"
    }
    currentCloudData = runCommand("apic cloud-settings:get --fields api_manager_endpoint,cloud_name --output - -s " + cloudAdminServer, False, 1, False)
    currentCloudData = yaml.safe_load(currentCloudData)
    apiMangerEndpoint = currentCloudData["api_manager_endpoint"]
    currentCloudName = currentCloudData["cloud_name"]

    # cloud name value is getting populated from the api manager endpoint
    cloudNameValue = urlparse(apiMangerEndpoint).hostname
    cloudNameFile = DATA_TEMP_DIR + "/cloudName.yaml"

    if currentCloudName != cloudNameValue:
        cloudNameUpdateData["cloud_name"] = cloudNameValue
        with open(cloudNameFile, 'w') as file:
                yaml.dump(cloudNameUpdateData, file, default_flow_style=False)
        print("Updating cloud name value with ", cloudNameValue)
        print()
        runCommand("apic cloud-settings:update --server " + cloudAdminServer + " " + cloudNameFile, False, 0, False)
    else:
        print("Not updating the clound name info. Current value: ",currentCloudName)
        print()

# start
def start():
    global cloudAdminServer
    
    print ("CHECKING IF KUBECTL/OC EXIST IN THE PATH AND HAVE ACCESS TO THE CLUSTER :")
    runKubernetesCommand("version", "default")
    
    print ("CHECKING IF APIC TOOLKIT IN THE PATH :: ")
    runCommand("apic version --accept-license --live-help=false")
    
    if args.skip_namespace_validation == False:
        validateNamespaces([args.mgmt_ns, args.ptl_ns, args.gw_ns])
    
    if args.mgmt_ns != None and "|" in args.mgmt_ns:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Invalid namespace({}) provided for management subsystem. Only one namespace need to be provided. Exiting...".format(args.mgmt_ns))
    healthCheck("mgmt", args.mgmt_ns)

    if not args.skip_gw:
        if args.gw_ns == None:
            print ("ACTION OUTPUT : Skipping health check for gateway subsytem as namespace is NOT provided in the input. Given namespace is {}".format(args.gw_ns))
        else:
            multipleNS = args.gw_ns.split("|")
            for ns in multipleNS:
                healthCheck("gw", ns)
    else:
        print("ACTION OUTPUT : Skipped health check for gateway subsystem as -skip_gw or --skip_gateway flag is set.")
        
    if not args.skip_ptl:
        if args.ptl_ns == None:
            print ("ACTION OUTPUT : Skipping health check for portal subsytem as namespace is NOT provided in the input. Given namespace is {}".format(args.ptl_ns))
        else:
            multipleNS = args.ptl_ns.split("|")
            for ns in multipleNS:
                healthCheck("ptl", ns)
    else:
        print("ACTION OUTPUT : Skipped health check for portal subsystem as -skip_ptl or --skip_portal flag is set.")
    
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
            sys.exit("ERROR : Not a valid realm for the flag, Input realm value : [{}]	. Exiting...".format(args.realm))
        runCommand("apic login --server " + args.server + " --realm " + args.realm + " --username " + args.username + " --password '" + args.password + "'", False, 1)
    
    cloudAdminServer = args.server
    
    updateCloudData()
    registerGatewayServices()
    registerPortalServices()
    print()

    #OCP : update topCRName-mgmt-admin-pass secret with the correct password
    #CP4I : delete topCRName-configurator secret
    #CP4I : delete configurator job
    print("Update secret if APIC target system is on OCP:")
    updateData_OCPAndCP4i()

    if created > 0:


        print()
        print()
        print("This script performed the following actions in the target APIC system:")
        print("***********************************************************************")

        print("1. Checked the health of the management, portal and gateway subsystems in the target APIC system.")
        print("2. Registered the new gateways and portals in the target system.")
        print("3. If CP4I, deleted the configurator job so that it runs again and creates the common services user registry.")
        print()
        print("Next steps:")
        print("1. Login to Cloud Manager UI on the target APIC system and verify that the new portals and gateways are available (the old gateway and portal still exist at this time).")
        print("2. Run the update_to_new_portals.py script to update the portal information in every catalog/provider_org to point to the new portals.")
        print("    -  Two ways to run the update_to_new_portals.py script")
        print("    -  Interactive mode : Prompts the user to enter credentials for every provider org.")
        print("    -  Silent mode : Using the -silent flag and the provider_org_credentials.yaml file containing the credentials for every provider org. Check the yaml for correct credentials before running the script.")
    else:
        print("ACTION OUTPUT : No new data got created.")
    print()


    
	
parser = argparse.ArgumentParser(description="The script is used in form factor to form factor migration to register gateway, portal services with the management subsystem of the target APIC system.\n\
Running this script is not required for CP4I as the configurator job takes care of the registering the services. For other form factors, run this script \n\
to register portal and gateway services with the management subsystem. \n \n\
Prerequisites ::\n\
1. Access to the cluster(target system) using kubectl or oc,\n\
2. Python 3.x and PyYAML module need to be installed\n\
3. Right version of apic toolkit must be in the path to run apic commands\n\
4. This script must be run on the target APIC system AFTER the management database from source system has been restored.\n\
5. The gateway and portal subsystems that need to be registered must be in healthy state.\n\
6. Keep the hostnames ready/handy for the new gateway and portal services so that they can be registered by running this script.\n\
7. The data directory where the configuration from the source system are saved. The data directory with source configuration  must be present in the same directory as this script." , 
formatter_class=argparse.RawDescriptionHelpFormatter)


parser.add_argument("-n", "--namespace", dest = "ns", help="uses this namespace value for all subsystems if individual subsystem namespace is not provided. Used for health check.")
parser.add_argument("-mgmt_ns", "--management_namespace", dest = "mgmt_ns", help="namespace of the management subsystem used for health check. This has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-ptl_ns", "-portal_namespace", dest = "ptl_ns", help="namespace of the portal subsystem used for health check. If portals in multiple namespaces, use pipe(|) to separate each namespace. This has more precedence than default -n or --namespace.")
parser.add_argument("-gw_ns", "--gateway_namespace", dest = "gw_ns", help="namespace of the gateway subsystem used for health check. If gateways in multiple namespaces, use pipe(|) to separate each namespace. This has more precedence than default -n or --namespace.")

parser.add_argument("-u", "--username", dest = "username", help="username to login to the cloud manager UI.")
parser.add_argument("-p", "--password", dest = "password", help="password to login to the cloud manager UI.")
parser.add_argument("-s", "--server", dest = "server", help="hostname to connect to cloud manager. Use platform api hostname.")
parser.add_argument("-r", "--realm", dest = "realm", help="name of the realm the user belongs to.")
parser.add_argument("-sso", "--sso", dest = "sso", action='store_true', help="Authentication using sso/oidc.")
parser.add_argument("-api_key", "--api_key", dest = "api_key", help="api key used in sso authentication for cloud manager.")

parser.add_argument('-skip_namespace_validation', "--skip_namespace_validation",  action='store_true', dest = "skip_namespace_validation", help='Skips validation of input namespaces.')

parser.add_argument('-skip_ptl', "--skip_portal",  action='store_true', dest = "skip_ptl", help='skips registering portal services.')
parser.add_argument('-skip_gw', "--skip_gateway", action='store_true', dest = "skip_gw", help='skips registering gateway services.')
parser.add_argument('-ignore_health_check', "--ignore_health_check", action='store_true', dest = "ignore_health_check", help='ignores health check status for each subsystem and proceeds.')
parser.add_argument('-ignore_version_check', "--ignore_version_check", action='store_true', dest = "ignore_version_check", help='ignores version match between source and target systems.')

parser.add_argument('-silent', "--silent", action='store_true', dest = "silent", help='Does not prompt for additinal inputs and proceeds silently.')
parser.add_argument('-mgmt_subsys_name', "--mgmt_subsystem_name", dest = "mgmt_subsystem_name", help='If multiple management subsytems present in the configuration, the script will use this.')


args = parser.parse_args()

print ("Start time :", time.asctime())
print ()

print ("Input namespace provided for all subsystems (-n or --namespace flag) : ", args.ns)
print ("Input namespace provided for management subsystem  (-mgmt_ns or --management_namespace flag) : ", args.mgmt_ns)
print ("Input namespace provided for portal subsystem (-ptl_ns or --portal_namespace flag) : ", args.ptl_ns)
print ("Input namespace provided for gateway subsystem (-gw_ns or --gateway_namespace flag) : ", args.gw_ns)
print ()

print ("Host name to connect to cloud manager (-s or --server flag) : ", args.server)
print ("Realm to which user belongs (-r or --realm flag) : ", args.realm)
print ("Cloud manager UI username (-u or --username flag) : ", args.username)
print ("Cloud manager UI password (-p or --password flag) : ********")
print ("SSO flag (-sso or --sso flag) : ", args.sso)
print ("api key (-api_key or --api_key flag) : ", args.api_key)
print ()

print ("skip portal service registrations (-skip_ptl or --skip_portal flag) : ", args.skip_ptl)
print ("skip gateway service registrations (-skip_gw or --skip_gateway flag) : ", args.skip_gw)
print ("Ignore health check status for each subsystem (-ignore_health_check or --ignore_health_check flag) : ", args.ignore_health_check)
print ("Ignore version match check (-ignore_version_check or --ignore_version_check flag) : ", args.ignore_version_check)
print ()

print ("silent (-silent or --silent flag) : ", args.silent)
print ("Mangement subsystem name (-mgmt_subsys_name or --mgmt_subsystem_name flag) : ", args.mgmt_subsystem_name)
print ()

forceLogPasswords = os.getenv("FORCE_LOG_PASSWORDS")

if args.mgmt_ns == None:
    print ("management namespace not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.mgmt_ns = args.ns

if args.gw_ns == None:
    print ("gateway namespace not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.gw_ns = args.ns
    
if args.ptl_ns == None:
    print ("portal namespace not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.ptl_ns = args.ns

print ()
print ("namespace used for management subsystem : ", args.mgmt_ns)
print ("namespace used for portal subsystem : ", args.ptl_ns)
print ("namespace used for gateway subsystem : ", args.gw_ns)
print ()

if args.server == None:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : Server(-s or --server flag) value are needed to register gateway and portal services. Exiting...")
    
if args.sso == False and (args.realm == None or args.username == None or args.password == None):
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : SSO flag is false. Its username/password based authentication. Realm(-r or --realm flag) , Username(-u or --username flag) and password(-p or --password flag) are needed for registering gateway and portal services. Exiting...")

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


if args.silent:
    # load gateway_portal_mapping.yaml file if it exists
    if os.path.exists(GATEWAY_PORTAL_MAPPING_FILENAME):
        print ("gateway_portal_mapping.yaml file exists. Loading it")
        text_file = open(GATEWAY_PORTAL_MAPPING_FILENAME, "r")
        config1 = text_file.read()
        print("gateway and portal mapping : \n", config1)
        gateway_portal_mapping = yaml.safe_load(config1)
        text_file.close()
    else:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : gateway_portal_mapping.yaml file does not exist. This file is needed when running in silent mode. Exiting...")

start();

print ("End time :", time.asctime())