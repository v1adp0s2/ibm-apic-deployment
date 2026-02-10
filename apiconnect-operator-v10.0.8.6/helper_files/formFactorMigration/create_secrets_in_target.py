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

subsystems = ("mgmt", "ptl", "gw", "a7s")



oc_client = "oc"
kubectl_client = "kubectl"
client = oc_client

pwd = None
DATA_DIR = None
DATA_TEMP_DIR = None
CONFIG_FILE_NAME = "config.yaml"
CONFIG_PORTAL_FILE_NAME = "config_portal.yaml"
config = None
config_portal = None

managementSecretsValidate = {
    "atm-cred": False, 
    "ccli-cred": False, 
    "cui-cred": False, 
    "dsgr-cred": False, 
    "juhu-cred": False, 
    "cli-cred": False, 
    "ui-cred": False
}

#The secret name is stored in configs
frontend_mgmt_certs = ["admin", "apiManager", "consumerApi", "platformApi", "analytics_ingestion_client", "gateway_client_client", "portal_admin_client"] # last 3 certs for sub system communication
frontend_mgmt_certs_optional = ["hub", "turnstile"] 
frontend_ptl_certs = ["portalDirector", "portalWeb"]
frontend_a7s_certs = ["aiEndpoint"]
frontend_gw_certs = ["gatewayManager", "gateway", "apicGatewayServiceTLS", "apicGatewayPeeringTLS"] # gatewayService and gatewayPeering also have ingress-ca as root


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

def applyFrontendCertificate(namespace, name, directoryPath, optional, obj):
    if name in obj:
        fullSecretName = directoryPath + "secret_" + obj[name] + ".yaml"
        fullCertName = directoryPath + "cert_" + obj[name] + ".yaml"

        if os.path.exists(fullSecretName) == False:
            print ("Time when error occurred :", time.asctime())
            sys.exit("ERROR :  secret file name ({}) does not exist. Exiting...".format(fullSecretName))
        runKubernetesCommand("apply -f " + fullSecretName, namespace)

        if args.skip_cert == False:
            if os.path.exists(fullCertName) == False:
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR :  Certificate file name ({}) does not exist. Exiting...".format(fullCertName))
            runKubernetesCommand("apply -f " + fullCertName, namespace)
    else:
        if optional:
            print("Skipping applying secret for name {} as it is not present in the config.".format(name))
        else:
            print ("Time when error occurred :", time.asctime())
            sys.exit("ERROR : Secret name not found for {} in the config. Exiting...".format(name))

def applyIngressCertificate(namespace, name, directoryPath, obj):
    if name in obj:
        fullSecretName = directoryPath + obj[name]
        fullCertName = directoryPath + obj["ingress_ca_cert"]

        if os.path.exists(fullSecretName) == False:
            print ("Time when error occurred :", time.asctime())
            sys.exit("ERROR :  ingress-ca secret file name ({}) does not exist. Exiting...".format(fullSecretName))
        runKubernetesCommand("apply -f " + fullSecretName, namespace)

        if args.skip_cert == False:
            if os.path.exists(fullCertName) == False:
               print("WARNING : ingress-ca cerficate does not exist")
            else:
                runKubernetesCommand("apply -f " + fullCertName, namespace)
    else:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : ingess-ca secret name not found in the config. Exiting...")

def applyInternalCertificate(namespace, directoryPath, obj):
    if "customCertificates" in obj:
        for each in obj["customCertificates"]:
            name = each["name"]

            fullSecretName = directoryPath + "secret_" + each["secretName"] + ".yaml"
            if name == "PGOTLSCertificate":
                fullCertName = directoryPath + "cert_postgres-operator.yaml"
            else:
                fullCertName = directoryPath + "cert_" + each["secretName"] + ".yaml"

            if os.path.exists(fullSecretName) == False:
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR :  secret file name ({}) does not exist. Exiting...".format(fullSecretName))
            runKubernetesCommand("apply -f " + fullSecretName, namespace)

            if args.skip_cert == False:
                if os.path.exists(fullCertName) == False:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR :  Certificate file name ({}) does not exist. Exiting...".format(fullCertName))
                runKubernetesCommand("apply -f " + fullCertName, namespace)
    else:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : customCertificates not found in the config while creating certificates. Exiting...")


def getSubsystemName(subsystemType, inputSubsystemName, flagInfo):
    subsystemNamesInConfig = None 
    if subsystemType == "portal_subsystem":
        subsystemNamesInConfig = list(config_portal[subsystemType].keys())
    else:
        subsystemNamesInConfig = list(config[subsystemType].keys())

    selectedSubsystem = None
    if len(subsystemNamesInConfig) > 1:
        print ()
        print ("List of subsystems from the saved configuration(source system) : ", subsystemNamesInConfig)
        if args.silent:
            selectedSubsystem = inputSubsystemName
        else:
            selectedSubsystem = input("SELECT THE SUBSYSTEM FROM THE LIST : ")

        if selectedSubsystem != None: selectedSubsystem = selectedSubsystem.strip()
        if selectedSubsystem not in subsystemNamesInConfig:
            if args.silent and selectedSubsystem == None:
                print("Multiple subsystems found in the saved configuration. You need to select one by using flags, {}".format(flagInfo))
            print ("Time when error occurred :", time.asctime())  
            sys.exit("ERROR : The selected subsystem({}) does not exist in the configuration. Exiting...".format(selectedSubsystem))

    elif len(subsystemNamesInConfig) == 1:
        selectedSubsystem = subsystemNamesInConfig[0]
    return selectedSubsystem


# start
def start():

    print ("CHECKING IF KUBECTL/OC EXIST IN THE PATH AND HAVE ACCESS TO THE CLUSTER :")
    runKubernetesCommand("version", "default")
    #print (config)
    #print (config_portal)
    
    print ("namespace used for management subsystem where the secrets are to be created: ", args.mgmt_ns)
    print ("namespace used for portal subsystem where the secrets are to be created: ", args.ptl_ns)
    print ("namespace used for gateway subsystem where the secrets are to be created: ", args.gw_ns)
    print ("namespace used for analytics subsystem where the secrets are to be created: ", args.a7s_ns)
    print ("")
    
    if args.skip_namespace_validation == False:
        validateNamespaces([args.mgmt_ns, args.ptl_ns])

    if args.mgmt_ns != None and "|" in args.mgmt_ns:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Invalid namespace({}) provided for management subsystem. Only one namespace need to be provided. Exiting...".format(args.mgmt_ns))
    
    if args.ptl_ns != None and "|" in args.ptl_ns:
        print ("Time when error occurred :", time.asctime())
        sys.exit("ERROR : Invalid namespace({}) provided for portal subsystem. Only one namespace need to be provided. Exiting...".format(args.ptl_ns))
    
    print ("Selecting management subsystem name from the config:")
    # need mgmt subsystem name, even for other subsystems for applying ingress-ca
    selectedSubsystem = getSubsystemName("management_subsystem", args.mgmt_subsystem_name, "-mgmt_subsys_name or --mgmt_subsystem_name")
    print ("ACTION OUTPUT : selected management subsystem from the source configuration : ", selectedSubsystem)
    ingressCADirectoryPath = DATA_DIR + "/" + selectedSubsystem + "/"
    print ("ACTION OUTPUT : ingress-ca directory path : ", ingressCADirectoryPath)

    if args.skip_mgmt == False:
        # management subsystem secrets	
        
        print("management subsystem::")
        print("**********************")
        if selectedSubsystem != None and args.mgmt_ns != None:
            mgmtSubsystemDetails = config["management_subsystem"][selectedSubsystem]    
                        
            print()
            print ("ACTION OUTPUT : management subsystem namespace for creating secrets : ", args.mgmt_ns)
            print()


            # check if management encryption secret exist
            if "encryptionSecret" not in mgmtSubsystemDetails:
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR : {} does not exist in the configuration for the management subsystem with name {}. Exiting...".format("encryptionSecret", selectedSubsystem))
            secretFile = DATA_DIR + "/" + selectedSubsystem + "/" + mgmtSubsystemDetails["encryptionSecret"]["secretName"] + ".yaml"
            if os.path.exists(secretFile) == False:
                print ("Time when error occurred :", time.asctime())
                sys.exit("ERROR :  Secret file({}) does not exist for the secret({}) in the data directory. Selected management subsystem is {}. Exiting...".format(secretFile, mgmtSubsystemDetails["encryptionSecret"]["secretName"], selectedSubsystem))

            #management encryption  secret
            runKubernetesCommand("apply -f " + secretFile, args.mgmt_ns)

            versionReconciled = None
            if "versionReconciled" in mgmtSubsystemDetails:
                versionReconciled = mgmtSubsystemDetails["versionReconciled"]
            print ("version reconciled : ", versionReconciled)
            
            if versionReconciled != None and versionReconciled.startswith("10."):
                # check if application credentials exist
                if "customApplicationCredentials" not in mgmtSubsystemDetails:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("{} does not exist in the configuration for the management subsystem with name {}. Exiting...".format("customApplicationCredentials", selectedSubsystem))
                else:
                    for each in mgmtSubsystemDetails["customApplicationCredentials"]:
                        if "name" in each and "secretName" in each:
                            secretFile = DATA_DIR + "/" + selectedSubsystem + "/" + each["secretName"] + ".yaml"
                            if os.path.exists(secretFile) == False:
                                print ("Time when error occurred :", time.asctime())
                                sys.exit("ERROR : Secret file({}) does not exist for the secret({}) in the data directory. Selected management subsystem is {}. Exiting...".format(secretFile, each["name"], selectedSubsystem))
                            else:
                                if each["name"] in managementSecretsValidate:
                                    managementSecretsValidate[each["name"]] = True
                
                for each in managementSecretsValidate:
                    if managementSecretsValidate[each] == False:
                        print ("Time when error occurred :", time.asctime())
                        sys.exit("ERROR : {} does not exist in the configuration for the management subsystem with name {}. Exiting...".format(each, selectedSubsystem))

                #create application credentials secrets
                for each in mgmtSubsystemDetails["customApplicationCredentials"]:
                    secretFile = DATA_DIR + "/" + selectedSubsystem + "/" + each["secretName"] + ".yaml"
                    runKubernetesCommand("apply -f " + secretFile, args.mgmt_ns)
            else:
                print ("ACTION OUTPUT : customApplicationCredentials not found. Looks like source environment is v2018. Source version : ", versionReconciled)
                print()

            # condition for RI stack(management backup not present in RI stack)
            if "databaseBackup" in mgmtSubsystemDetails and "credentials" in mgmtSubsystemDetails["databaseBackup"]:
                dbBackupSecretFile = DATA_DIR + "/" + selectedSubsystem + "/" + mgmtSubsystemDetails["databaseBackup"]["credentials"] + ".yaml"
                if os.path.exists(secretFile) == False:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Secret file({}) does not exist for the secret({}) in the data directory. Selected management subsystem is {}. Exiting...".format(dbBackupSecretFile, mgmtSubsystemDetails["databaseBackup"]["credentials"], selectedSubsystem))

                #management db backup credentials secret
                runKubernetesCommand("apply -f " + dbBackupSecretFile, args.mgmt_ns)


            if args.apply_frontend_certificates:
                applyIngressCertificate(args.mgmt_ns, "ingress_ca_secret", ingressCADirectoryPath, mgmtSubsystemDetails)

                print("management subsystem FRONTEND CERTIFICATES ::")
                for eachName in frontend_mgmt_certs:
                    applyFrontendCertificate(args.mgmt_ns, eachName, DATA_DIR + "/" + selectedSubsystem + "/cert_frontend/", False, mgmtSubsystemDetails)
                print()
                for eachName in frontend_mgmt_certs_optional:
                    applyFrontendCertificate(args.mgmt_ns, eachName, DATA_DIR + "/" + selectedSubsystem + "/cert_frontend/", True, mgmtSubsystemDetails)

            print()
            if args.apply_internal_certificates:
                print("management subsystem INTERNAL CERTIFICATES ::")
                applyInternalCertificate(args.mgmt_ns, DATA_DIR + "/" + selectedSubsystem + "/cert_internal/", mgmtSubsystemDetails)

        else:
            print ("ACTION OUTPUT : Not applying secrets in target namespace for management subsystem. check values for source management subsystem name : {} and target management subsytem namespace : {}".format(selectedSubsystem, args.mgmt_ns))
    else:
        print("ACTION OUTPUT : Skipped creating secrets for management subsystem as skip_mgmt/skip_mamangement flag is set.")
        
        
    if args.skip_ptl == False:
        if config_portal != None:
            # portal subsystem secrets	

            print()
            print("portal subsystem::")
            print("******************")
            print ("Selecting portal subsystem name from the config:")
            selectedSubsystem = getSubsystemName("portal_subsystem", args.ptl_subsystem_name, "-ptl_subsys_name or --ptl_subsystem_name")
            print ("ACTION OUTPUT : selected portal subsystem from the source configuration : ", selectedSubsystem)
        
            if selectedSubsystem != None and args.ptl_ns != None:
                portalSubsystemDetails = config_portal["portal_subsystem"][selectedSubsystem]
                    
                print()
                print ("ACTION OUTPUT : portal subsystem namespace for creating secrets : ", args.ptl_ns)
                print()
            
                # check if portal encryption secret exist
                if "encryptionSecret" not in portalSubsystemDetails:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("{} does not exist in the configuration for the portal subsystem with name {}. Exiting...".format("encryptionSecret", selectedSubsystem))
                secretFile = DATA_DIR + "/" + selectedSubsystem + "/" + portalSubsystemDetails["encryptionSecret"]["secretName"] + ".yaml"
                if os.path.exists(secretFile) == False:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Secret file({}) does not exist for the secret({}) in the data directory. Selected portal subsystem is {}. Exiting...".format(secretFile, portalSubsystemDetails["encryptionSecret"]["secretName"], selectedSubsystem))
    	
                #portal encryption secret
                runKubernetesCommand("apply -f " + secretFile, args.ptl_ns)
                	
                if ("portalBackup" not in portalSubsystemDetails) or ("credentials" not in portalSubsystemDetails["portalBackup"]) :
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("{} does not exist in the configuration for the portal subsystem with name {}. Exiting...".format("portalBackup/credentials", selectedSubsystem))
                secretFile = DATA_DIR + "/" + selectedSubsystem + "/" + portalSubsystemDetails["portalBackup"]["credentials"] + ".yaml"
                if os.path.exists(secretFile) == False:
                    print ("Time when error occurred :", time.asctime())
                    sys.exit("ERROR : Secret file({}) does not exist for the secret({}) in the data directory. Selected portal subsystem is {}. Exiting...".format(secretFile, portalSubsystemDetails["portalBackup"]["credentials"], selectedSubsystem))    

            
                #portal db backup credentials secret
                runKubernetesCommand("apply -f " + secretFile, args.ptl_ns)

                if args.apply_frontend_certificates:
                    applyIngressCertificate(args.ptl_ns, "ingress_ca_secret", ingressCADirectoryPath, mgmtSubsystemDetails)

                    print("portal subsystem FRONTEND CERTIFICATES ::")
                    for eachName in frontend_ptl_certs:
                        applyFrontendCertificate(args.ptl_ns, eachName, DATA_DIR + "/" + selectedSubsystem + "/cert_frontend/", False, portalSubsystemDetails)

                print()
                if args.apply_internal_certificates:
                    print("portal subsystem INTERNAL CERTIFICATES ::")
                    applyInternalCertificate(args.ptl_ns, DATA_DIR + "/" + selectedSubsystem + "/cert_internal/", portalSubsystemDetails)

            else:
                print ("ACTION OUTPUT : Not applying secrets in target namespace for portal subsystem. Check values for source portal subsystem name : {} and target portal subsystem namespace : {}".format(selectedSubsystem, args.ptl_ns))
        else:
            print ("ACTION OUTPUT : Sources system portal configuration not found. Not creating secrets for portal subsystem")
    else:
        print("ACTION OUTPUT : Skipped creating secrets for portal subsystem as skip_ptl/skip_portal flag is set.")
    
    if args.apply_frontend_certificates or args.apply_internal_certificates:
        if args.skip_a7s == False:
            print()
            print("analytics subsystem::")
            print("*********************")
            print ("Selecting analytics subsystem name from the config:")
            selectedSubsystem = getSubsystemName("analytics_subsystem", args.a7s_subsystem_name, "-a7s_subsys_name or --a7s_subsystem_name")
            print ("ACTION OUTPUT : selected analytics subsystem from the source configuration : ", selectedSubsystem)

            if selectedSubsystem != None and args.a7s_ns != None:
                a7sSubsystemDetails = config["analytics_subsystem"][selectedSubsystem]
                        
                print()
                print ("ACTION OUTPUT : analytics subsystem namespace for creating secrets : ", args.a7s_ns)
                print()

                if args.apply_frontend_certificates:
                    applyIngressCertificate(args.a7s_ns, "ingress_ca_secret", ingressCADirectoryPath, mgmtSubsystemDetails)

                    for eachName in frontend_a7s_certs:
                        print("analytics subsystem FRONTEND CERTIFICATES ::")
                        applyFrontendCertificate(args.a7s_ns, eachName, DATA_DIR + "/" + selectedSubsystem + "/cert_frontend/", False, a7sSubsystemDetails)

                print()
                if args.apply_internal_certificates:
                    print("analytics subsystem INTERNAL CERTIFICATES ::")
                    applyInternalCertificate(args.a7s_ns, DATA_DIR + "/" + selectedSubsystem + "/cert_internal/", a7sSubsystemDetails)
        else:
            print("ACTION OUTPUT : Skipped creating certificates for analytics subsystem as skip_a7s/skip_analytics flag is set.")

        if args.skip_gw == False:
            print()
            print("gateway subsystem::")
            print("*******************")
            print ("Selecting gateway subsystem name from the config:")
            selectedSubsystem = getSubsystemName("gateway_subsystem", args.gw_subsystem_name, "-gw_subsys_name or --gw_subsystem_name")
            print ("ACTION OUTPUT : selected gateway subsystem from the source configuration : ", selectedSubsystem)

            if selectedSubsystem != None and args.gw_ns != None:
                gwSubsystemDetails = config["gateway_subsystem"][selectedSubsystem]

                print()
                print ("ACTION OUTPUT : gateway subsystem namespace for creating secrets : ", args.gw_ns)
                print()

                if args.apply_frontend_certificates:
                    applyIngressCertificate(args.gw_ns, "ingress_ca_secret", ingressCADirectoryPath, mgmtSubsystemDetails)

                    print("gateway subsystem FRONTEND CERTIFICATES ::")
                    for eachName in frontend_gw_certs:
                        applyFrontendCertificate(args.gw_ns, eachName, DATA_DIR + "/" + selectedSubsystem + "/cert_frontend/", False, gwSubsystemDetails)
                print()
        else:
            print("ACTION OUTPUT : Skipped creating certificates for gateway subsystem as skip_gw/skip_gateway flag is set.")

    
    print()
    print()
    print("This script performed the following actions in the target cluster:")
    print("******************************************************************")
    print("1. Created the database backup credentials secret.")
    print("2. Created the custom application credentials and other secrets.")
    if args.apply_frontend_certificates:
        print("3. Applied frontend/ingress/external certificates/secrets.")
    if args.apply_internal_certificates:
        print("4. Applied internal certificates/secrets.")

    print()
    print("Next steps:")
    print("1. Install the target APIC cluster.")
    print("    -  If target cluster is OCP/CP4I, you can use the install_apic_on_ocp.py script to install or install manually (for advanced configurations) from OCP or CP4I UI.")
    print("    -  Its recommended to install the target system manually for customizing the configuration.")
    print("    -  For other form factors, install APIC manually in the target cluster.")
    print()
    print("Note : If installing manually, make sure the configuration from source system saved in data/config.yaml and data/config.portal_yaml is used while installing the target APIC cluster.")
    print("    -  For management subsystem : customApplicationCredentials, databaseBackup, encryptionSecret, name, originalUID and siteName.")
    print("    -  For portal subsystem : portalBackup, encryptionSecret, name, originalUID and siteName.")
    print()
	
parser = argparse.ArgumentParser(description="The script is used in form factor to form factor migration. The secrets obtained from the source system for management and portal subsystems \n\
are created in the target system in the specified namespace. The script has to be run once the namespace is created and before API Connect is installed.\n\n\
Prerequisites ::\n\
1. Access to the cluster(target system) using kubectl or oc,\n\
2. Python 3.x and PyYAML module need to be installed\n\
3. The data directory where the secrets from the source system are saved. The data directory with source configuration must be present in the same directory as this script.", 
formatter_class=argparse.RawDescriptionHelpFormatter)


parser.add_argument("-n", "--namespace", dest = "ns", help="uses this namespace value for all subsystems if individual subsystem namespace is not provided.")
parser.add_argument("-mgmt_ns", "--management_namespace", dest = "mgmt_ns", help="namespace of the management subsystem. This has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-ptl_ns", "-portal_namespace", dest = "ptl_ns", help="namespace of the portal subsystem. This has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-gw_ns", "--gateway_namespace", dest = "gw_ns", help="namespace of the gateway subsystem. This value has more precedence than the common flag, -n or --namespace.")
parser.add_argument("-a7s_ns", "--analytics_namespace", dest = "a7s_ns", help="namespace of the analytics subsystem. This value has more precedence than the common flag, -n or --namespace.")

parser.add_argument('-skip_mgmt', "--skip_management", action='store_true', dest = "skip_mgmt", help='Skips applying secrets for management subsystem.')
parser.add_argument('-skip_ptl', "--skip_portal",  action='store_true', dest = "skip_ptl", help='Skips applying secrets for portal subsystem.')
parser.add_argument('-skip_gw', "--skip_gateway", action='store_true', dest = "skip_gw", help='skips gateway subsystem.')
parser.add_argument('-skip_a7s', "--skip_analytics", action='store_true', dest = "skip_a7s", help='skips analytics subsystem.')

parser.add_argument('-skip_namespace_validation', "--skip_namespace_validation",  action='store_true', dest = "skip_namespace_validation", help='Skips validation of input namespaces.')

parser.add_argument('-silent', "--silent", action='store_true', dest = "silent", help='Does not prompt for additinal inputs and proceeds silently.')
parser.add_argument('-mgmt_subsys_name', "--mgmt_subsystem_name", dest = "mgmt_subsystem_name", help='If multiple management subsytems present in the configuration, the script will use this.')
parser.add_argument('-ptl_subsys_name', "--ptl_subsystem_name", dest = "ptl_subsystem_name", help='If multiple portal subsytems present in the configuration, the script will use this.')
parser.add_argument('-a7s_subsys_name', "--a7s_subsystem_name", dest = "a7s_subsystem_name", help='If multiple analytics subsytems present in the configuration, the script will use this.')
parser.add_argument('-gw_subsys_name', "--gw_subsystem_name", dest = "gw_subsystem_name", help='If multiple gateway subsytems present in the configuration, the script will use this.')

parser.add_argument('-apply_frontend_certificates', "--apply_frontend_certificates", action='store_true', dest = "apply_frontend_certificates", help='Applies external/frontend/ingress secrets for all subsystems. Applies corresponding certificate kind too. To skip applying Certificate kind use -skip_cert')
parser.add_argument('-apply_internal_certificates', "--apply_internal_certificates", action='store_true', dest = "apply_internal_certificates", help='Applies internal secrets for all subsystems. Applies corresponding certificate kind too. To skip applying Certificate kind use -skip_cert')
parser.add_argument('-skip_cert', "--skip_cert", action='store_true', dest = "skip_cert", help='Skips applying Certificate kind. Only Secret kind secrets are applied')


args = parser.parse_args()

print ("Start time :", time.asctime())
print ()

print ("Input namespace provided for all subsystems (-n or --namespace flag) : ", args.ns)
print ("Input namespace provided for management subsystem (-mgmt_ns or --management_namespace flag) : ", args.mgmt_ns)
print ("Input namespace provided for portal subsystem (-ptl_ns or --portal_namespace flag) : ", args.ptl_ns)
print ("Input namespace provided for gateway subsystem (-gw_ns or --gateway_namespace flag) : ", args.gw_ns)
print ("Input namespace provided for analytics subsystem (-skip_a7s or --analytics_namespace flag) : ", args.a7s_ns)
print ()

print ("skip creating secrets for management subsystem (-skip_mgmt or --skip_management flag) : ", args.skip_mgmt)
print ("skip creating secrets for portal subsystem  (-skip_ptl or --skip_portal flag) : ", args.skip_ptl)
print ("skip creating secrets for gateway subsystem  (-skip_gw or --skip_gateway flag) : ", args.skip_gw)
print ("skip creating secrets for analytics subsystem  (-skip_a7s or --skip_analytics flag) : ", args.skip_a7s)
print ()

print ("silent (-silent or --silent flag) : ", args.silent)
print ("Mangement subsystem name (-mgmt_subsys_name or --mgmt_subsystem_name flag) : ", args.mgmt_subsystem_name)
print ("Portal subsystem name (-ptl_subsys_name or --ptl_subsystem_name flag) : ", args.ptl_subsystem_name)
print ("Analytics subsystem name (-a7s_subsys_name or --a7s_subsystem_name flag) : ", args.a7s_subsystem_name)
print ("Gateway subsystem name (-gw_subsys_name or --gw_subsystem_name flag) : ", args.gw_subsystem_name)
print ()

print ("Apply frontend/ingress/external certs/secrets (-apply_frontend_certificates or --apply_frontend_certificates flag) : ", args.apply_frontend_certificates)
print ("Apply internal certs/secrets (-apply_internal_certificates or --apply_internal_certificates flag) : ", args.apply_internal_certificates)
print ("Skip Cerificate kind (-skip_cert or --skip_cert flag) : ", args.skip_cert)


if args.mgmt_ns == None:
    print ("management namespace not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.mgmt_ns = args.ns

if args.ptl_ns == None:
    print ("portal namespace not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.ptl_ns = args.ns

if args.gw_ns == None:
    print ("gateway namespace not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.gw_ns = args.ns

if args.a7s_ns == None:
    print ("analytics namespace not provided. Defaulting to flag -n or --namespace if provided which is applicable for all subsystems.")
    args.a7s_ns = args.ns

print ()
print ("namespace used for management subsystem : ", args.mgmt_ns)
print ("namespace used for portal subsystem : ", args.ptl_ns)
print ("namespace used for gateway subsystem : ", args.gw_ns)
print ("namespace used for analytics subsystem : ", args.a7s_ns)
print ()

pwd = os.getcwd()
DATA_DIR = pwd + "/data"
DATA_TEMP_DIR = pwd + "/data/temp"

# load config data if exists
if os.path.exists(DATA_DIR + "/" + CONFIG_FILE_NAME):
    print ("Source APIC system configuration file exists. Loading it")
    text_file = open(DATA_DIR + "/" + CONFIG_FILE_NAME, "r")
    config1 = text_file.read()
    print("management configuration file : ", config1)
    config = yaml.safe_load(config1)
    text_file.close()
else:
    print ("Time when error occurred :", time.asctime())
    sys.exit("ERROR : config.yaml file with details of the source APIC system in NOT present in the data directory. Exiting...")

print()
if os.path.exists(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME):
    print ("Source APIC system portal configuration file exists. Loading it")
    text_file2 = open(DATA_DIR + "/" + CONFIG_PORTAL_FILE_NAME, "r")
    config2 = text_file2.read()
    print("portal configuration : ", config2)
    config_portal = yaml.safe_load(config2)
    text_file2.close()
else:
    print ("portal configuration from source system not existing.")
print()
    
start();

print()
print ("End time :", time.asctime())