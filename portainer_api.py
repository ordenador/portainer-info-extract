import requests


class PortainerAPI:
    def __init__(self, url, username, password):
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.base_url = url
        self.username = username
        self.password = password
        self.jwt = self.authenticate()
        self.request_errors = []

    def authenticate(self):
        """ Authenticate and return JWT token """
        login_url = f"{self.base_url}/api/auth"
        credentials = {"Username": self.username, "Password": self.password}
        response = requests.post(login_url, json=credentials)
        response.raise_for_status()
        return response.json()['jwt']

    def get_headers(self):
        """ Returns the authorization headers """
        return {"Authorization": f"Bearer {self.jwt}"}

    def safe_request(self, url):
        """ Perform a safe HTTP GET request and log errors """
        try:
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_details = {
                "URL": url,
                "Error": str(e)
            }
            self.request_errors.append(error_details)
            print(f"Request failed: {e}")
            return None

    def get_request_errors(self):
        """ Devuelve los errores registrados durante las solicitudes HTTP """
        return self.request_errors

    def get_endpoints(self):
        """ Get all endpoints """
        url = f"{self.base_url}/api/endpoints"
        return self.safe_request(url)

    def get_endpoint_groups(self):
        """ Get all endpoint groups """
        url = f"{self.base_url}/api/endpoint_groups"
        return self.safe_request(url)

    def get_services(self, endpoint_id):
        """ Get services for a specific endpoint """
        return self.get_endpoint_data(endpoint_id, "services")

    def get_secrets(self, endpoint_id):
        """ Get secrets for a specific endpoint """
        return self.get_endpoint_data(endpoint_id, "secrets")

    def get_nodes(self, endpoint_id):
        """ Get nodes for a specific endpoint """
        return self.get_endpoint_data(endpoint_id, "nodes")

    def get_containers(self, endpoint_id):
        """ Get a list of containers for a specific endpoint """
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json"
        return self.safe_request(url)

    def get_container_stats(self, endpoint_id, container_id):
        """ Get container statistics for a specific container """
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stats?stream=false"
        return self.safe_request(url)

    def get_endpoint_data(self, endpoint_id, data_type):
        """ Get data (services, secrets, etc.) for a specific endpoint """
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/{data_type}"
        return self.safe_request(url)

    def get_group_name(self, group_id):
        """ Get the name of a group by its ID """
        groups = self.get_endpoint_groups()
        for group in groups:
            if group["Id"] == group_id:
                return group["Name"]
        return "Unknown Group"
