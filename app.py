import requests
import os
import json
import pandas as pd

# Configuration using environment variables
url_portainer = os.environ.get('PORTAINER_HOST')
username = os.environ.get('PORTAINER_USER')
password = os.environ.get('PORTAINER_PASSWORD')

# Ensure the URL has the correct scheme
if not url_portainer.startswith(('http://', 'https://')):
    url_portainer = 'https://' + url_portainer

# Check that all environment variables are defined
if not url_portainer or not username or not password:
    raise ValueError("One or more required environment variables are not defined.")

# Portainer URLs
LOGIN_URL = f"{url_portainer}/api/auth"
ENDPOINTS_URL = f"{url_portainer}/api/endpoints"

# Credentials for authentication
credentials = {
    "Username": username,
    "Password": password
}

# Request JWT
jwt_response = requests.post(LOGIN_URL, json=credentials)
jwt_response.raise_for_status()
jwt = jwt_response.json()['jwt']

# Generate the header to be used for all queries
headers = {"Authorization": f"Bearer {jwt}"}

# Get all endpoints available in Portainer
endpoint_response = requests.get(ENDPOINTS_URL, headers=headers)
endpoint_response.raise_for_status()
endpoints = endpoint_response.json()

# Lista para almacenar errores
request_errors = []

# Función modificada para hacer requests seguros
def safe_request(url, headers):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as err:
        error_details = {
            "URL": url,
            "Error": str(err)
        }
        request_errors.append(error_details)
        print(f"HTTP Error when accessing {url}: {err}")
        return None



# Get information about groups
groups_url = f"{url_portainer}/api/endpoint_groups"
groups_response = requests.get(groups_url, headers=headers)
groups_response.raise_for_status()
groups = groups_response.json()

# Create a dictionary to map group ID to group name
group_id_to_name = {group["Id"]: group["Name"] for group in groups}

services_data = []
secrets_data = []
nodes_dict = {}
container_stats_data = []


# Iterate through each endpoint and get additional information
for endpoint in endpoints:
    endpoint_id = endpoint["Id"]
    endpoint_name = endpoint["Name"]
    group_id = endpoint["GroupId"]
    group_name = group_id_to_name.get(group_id, "Unknown Group")  # Get the group name

    print(f"Endpoint: {endpoint_name} (ID: {endpoint_id}, Group: {group_name})")

    # Get Swarm services
    services_url = f"{url_portainer}/api/endpoints/{endpoint_id}/docker/services"
    services_response = safe_request(services_url, headers)
    if services_response is not None:
        for service in services_response:
            # Extract environment variable keys
            env_keys = [env.split('=')[0] for env in service["Spec"]["TaskTemplate"]["ContainerSpec"].get("Env", [])]

            # Extract only the 'image:tag' part of the full image string
            full_image = service["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]
            image_without_sha = full_image.split('@')[0]

            # Process configurations of each service
            config_details = []
            if "Configs" in service["Spec"]["TaskTemplate"]["ContainerSpec"]:
                for config in service["Spec"]["TaskTemplate"]["ContainerSpec"]["Configs"]:
                    config_detail = {
                        "ConfigName": config["ConfigName"],
                        "FilePath": config["File"]["Name"]
                    }
                    config_details.append(config_detail)

            # Process mounts of each service
            mounts_details = []
            if "Mounts" in service["Spec"]["TaskTemplate"]["ContainerSpec"]:
                for mount in service["Spec"]["TaskTemplate"]["ContainerSpec"]["Mounts"]:
                    mount_detail = {
                        "Source": mount["Source"],
                        "Target": mount["Target"],
                        "Type": mount["Type"]
                    }
                    mounts_details.append(mount_detail)

            # Process the stack
            labels = service["Spec"]["TaskTemplate"]["ContainerSpec"].get("Labels", {})
            stack = labels.get("com.docker.stack.namespace")

            # Create a simplified service object
            services_data.append({
                "Group": group_name,
                "Endpoint": endpoint_name,
                "Type": "Service",
                "Name": service["Spec"]["Name"],
                "Image": image_without_sha,
                "Environment_Variables": env_keys,
                "Configurations": config_details,
                "Mounts": mounts_details,
                "Replicas": service["Spec"]["Mode"]["Replicated"]["Replicas"],
                "Stack": stack
            })

    # Get Swarm secrets
    secrets_url = f"{url_portainer}/api/endpoints/{endpoint_id}/docker/secrets"
    secrets_response = safe_request(secrets_url, headers)
    if secrets_response is not None:
        # Collect secret names in a list
        secret_names = [secret["Spec"]["Name"] for secret in secrets_response]

        # Add the list of secret names as a single item
        secrets_data.append({
            "Endpoint": endpoint_name,
            "Type": "Secret",
            "Names": secret_names
        })


    # Get Swarm nodes
    nodes_url = f"{url_portainer}/api/endpoints/{endpoint_id}/docker/nodes"
    nodes_response = safe_request(nodes_url, headers)
    if nodes_response is not None:
        for node in nodes_response:
            hostname = node["Description"]["Hostname"]
            # Check if this node has been processed already
            if hostname not in nodes_dict:
                nodes_dict[hostname] = {
                    "Endpoint": endpoint_name,
                    "Type": "Node",
                    "Hostname": node["Description"]["Hostname"],
                    "Role": node["Spec"]["Role"],
                    "Availability": node["Spec"]["Availability"],
                    "NanoCPUs": node["Description"]["Resources"]["NanoCPUs"],
                    "MemoryBytes": node["Description"]["Resources"]["MemoryBytes"],
                    "State": node["Status"]["State"]
                }


    # Get the list of containers
    containers_url = f"{url_portainer}/api/endpoints/{endpoint_id}/docker/containers/json"
    containers_response = safe_request(containers_url, headers)
    
    if containers_response is not None:
        for container in containers_response:
            container_id = container["Id"]
            container_stack = container["Labels"].get("com.docker.stack.namespace", "Unknown")
            container_service = container["Labels"].get("com.docker.swarm.service.name", "Unknown")
        

            # Get container statistics
            stats_url = f"{url_portainer}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stats?stream=false"
            stats_response = safe_request(stats_url, headers)

            if stats_response is not None:
                container_stats_data.append({
                    "Endpoint": endpoint_name,
                    "Stack": container_stack,
                    "Service": container_service,
                    "stats": stats_response,
                })


# Convert lists to DataFrames
df_services = pd.DataFrame(services_data)
df_secrets = pd.DataFrame(secrets_data)
df_nodes = pd.DataFrame(nodes_dict.values())
df_container_stats = pd.DataFrame(container_stats_data)
df_request_errors = pd.DataFrame(request_errors)


# Asegúrate de incluir la escritura de este DataFrame en el archivo Excel
with pd.ExcelWriter("portainer_data.xlsx", engine='openpyxl') as writer:
    df_services.to_excel(writer, sheet_name="Services", index=False)
    df_secrets.to_excel(writer, sheet_name="Secrets", index=False)
    df_nodes.to_excel(writer, sheet_name="Nodes", index=False)
    df_container_stats.to_excel(writer, sheet_name="Container Statistics", index=False)
    df_request_errors.to_excel(writer, sheet_name="Request Errors", index=False)  # Nueva pestaña para errores

print("Data and request errors exported to 'portainer_data.xlsx'")