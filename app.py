from collections import defaultdict
from portainer_api import PortainerAPI
from urllib.parse import urlparse
import concurrent.futures
import os
import pandas as pd

url_portainer = os.environ.get('PORTAINER_HOST')
username = os.environ.get('PORTAINER_USER')
password = os.environ.get('PORTAINER_PASSWORD')

# Concurrency
num_workers = 32

# Check if all the necessary environment variables are defined
if not url_portainer or not username or not password:
    raise ValueError("One or more required environment variables are missing.")

# Extract the slug from the domain
parsed_url = urlparse(url_portainer)
domain_slug = parsed_url.netloc.split('.')[0]  # Extract the first part of the domain

# Create an instance of PortainerAPI
portainer_api = PortainerAPI(url_portainer, username, password)

# Get all the endpoints available in Portainer
endpoints = portainer_api.get_endpoints()

# Group endpoints by GroupId
endpoints_by_group = defaultdict(list)
for endpoint in endpoints:
    endpoints_by_group[endpoint["GroupId"]].append(endpoint)

# Data to collect
container_stats_data = []
nodes_dict = {}
request_errors = []
secrets_data = []
services_data = []
endpoints_data = []


def process_endpoint(endpoint):
    endpoint_id = endpoint["Id"]
    endpoint_name = endpoint["Name"]
    group_id = endpoint["GroupId"]
    group_name = portainer_api.get_group_name(group_id)

    # Append endpoint data to the endpoints_data list
    endpoints_data.append({
        "Endpoint_Id": endpoint_id,
        "Endpoint_Name": endpoint_name,
        "Group_Id": group_id,
        "Group_Name": group_name
    })

    print(f"Processing Endpoint: {endpoint_name} (ID: {endpoint_id}, Group: {group_name})")

    # Use the class methods to retrieve data
    services = portainer_api.get_services(endpoint_id)
    secrets = portainer_api.get_secrets(endpoint_id)
    nodes = portainer_api.get_nodes(endpoint_id)
    containers = portainer_api.get_containers(endpoint_id)

    # Process services
    if services:
        for service in services:
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

            mode = service["Spec"]["Mode"]
            if "Replicated" in mode:
                replicas = mode["Replicated"]["Replicas"]
            else:
                replicas = 0  # Or None, depending on how you want to handle non-replicated services

            # Process the stack
            labels = service["Spec"]["TaskTemplate"]["ContainerSpec"].get("Labels", {})
            stack = labels.get("com.docker.stack.namespace")

            # Create a simplified service object
            services_data.append({
                "Endpoint_Id": endpoint_id,
                "Endpoint": endpoint_name,
                "Group": group_name,
                "Stack": stack,
                "Name": service["Spec"]["Name"],
                "Replicas": replicas,
                "Image": image_without_sha,
                "Environment_Variables": env_keys,
                "Configurations": config_details,
                "Mounts": mounts_details
            })

    # Process secrets
    if secrets:
        # Collect secret names in a list
        secret_names = [secret["Spec"]["Name"] for secret in secrets]

        # Add the list of secret names as a single item
        secrets_data.append({
            "Endpoint": endpoint_name,
            "Type": "Secret",
            "Names": secret_names
        })

    # Process nodes
    if nodes:
        for node in nodes:
            hostname = node["Description"]["Hostname"]
            # Check if this node has been processed already
            if hostname not in nodes_dict:
                nodes_dict[hostname] = {
                    "Endpoint": endpoint_name,
                    "Hostname": node["Description"]["Hostname"],
                    "Role": node["Spec"]["Role"],
                    "Availability": node["Spec"]["Availability"],
                    "NanoCPUs": node["Description"]["Resources"]["NanoCPUs"],
                    "MemoryBytes": node["Description"]["Resources"]["MemoryBytes"],
                    "State": node["Status"]["State"]
                }

    if containers:
        for container in containers:
            container_id = container["Id"]
            container_stack = container["Labels"].get("com.docker.stack.namespace", "Unknown")
            container_service = container["Labels"].get("com.docker.swarm.service.name", "Unknown")

            # Get container statistics
            stats = portainer_api.get_container_stats(endpoint_id, container_id)
            if stats:
                container_stats_data.append({
                    "Endpoint": endpoint_name,
                    "Stack": container_stack,
                    "Service": container_service,
                    "stats": stats,
                })


def process_group(group_endpoints):
    for endpoint in group_endpoints:
        process_endpoint(endpoint)


with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
    futures = [executor.submit(process_group, group) for group in endpoints_by_group.values()]

request_errors = portainer_api.get_request_errors()

# Convert the collected data into DataFrames
df_services = pd.DataFrame(services_data)
df_secrets = pd.DataFrame(secrets_data)
df_nodes = pd.DataFrame(nodes_dict.values())
df_container_stats = pd.DataFrame(container_stats_data)
df_request_errors = pd.DataFrame(request_errors)
df_endpoints = pd.DataFrame(endpoints_data)


# Construct the filename with the domain slug
filename = f"portainer_data_{domain_slug}.xlsx"

# Export DataFrames to an Excel file
with pd.ExcelWriter(filename, engine='openpyxl') as writer:
    df_services.to_excel(writer, sheet_name="Services", index=False)
    df_secrets.to_excel(writer, sheet_name="Secrets", index=False)
    df_nodes.to_excel(writer, sheet_name="Nodes", index=False)
    df_container_stats.to_excel(writer, sheet_name="Container Statistics", index=False)
    df_request_errors.to_excel(writer, sheet_name="Request Errors", index=False)
    df_endpoints.to_excel(writer, sheet_name="Endpoints", index=False)

print(f"Data and request errors exported to '{filename}'")
