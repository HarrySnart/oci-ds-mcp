''' minimal example mcp server for interacting with OCI Data Science '''

import os
from fastmcp import FastMCP
import ads
from ads.catalog.project import ProjectCatalog
from ads.catalog.model import ModelCatalog
import logging 
from starlette.responses import JSONResponse
from typing import Any, Dict
import pandas as pd
import oci

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

mcp = FastMCP(name="OCI-Data-Science-MCP")

ads.set_auth("resource_principal")

def log_request(tool_name: str, **kwargs):
    logger.info(f"[REQUEST RECEIVED] Tool: {tool_name}, Args: {kwargs}")

def log_response(tool_name: str, result):
    logger.info(f"[RESPONSE SENT] Tool: {tool_name}, Result: {result}")


@mcp.tool()
def get_compartment_id() -> str:
    """ Get Compartment OCID for use with other tools. Important - use this tool to initialise the compartment_id variable. 
    
    Returns:
        compartment_id: OCI compartment ID
    """

    # initialise by dynamically getting the compartment OCID (this assumes Container Instances uses same compartment as OCI Data Science)
    signer = oci.auth.signers.get_resource_principals_signer()
    identity_client = oci.identity.IdentityClient(config={}, signer=signer)

    # Get the compartment OCID from resource principal
    compartment_id = signer.compartment_id
    return compartment_id


@mcp.tool()
def project_count(compartment_id) -> int:
    """Get count of OCI Data Science Projects
    
    Args:
        compartment_id: OCI compartment ID
    
    Returns:
        Number of projects in the compartment
    """
    
    logger.info("calling project_count tool successfully")
    
    try:
        project_catalog = ProjectCatalog(compartment_id=compartment_id)
        projects = project_catalog.list_projects()
        num_projects = len(project_catalog)
        return num_projects
    except Exception as e:
        print(f"Error getting project count: {e}")
        raise


@mcp.tool()
def create_project(project_name,project_description,compartment_id) -> Dict:
    """ Create new OCI Data Science Project with project name and description.
    
    Args:
        compartment_id: OCI compartment ID. 
        project_name: a name for the new project, for example 'Customer Churn Project'
        project_description: a description of the new project, for example 'Customer Churn modelling using binary classification'
    
    Returns:
        Dictionary of new project details
    """
    try:
        project_catalog = ProjectCatalog(compartment_id)
        res = project_catalog.create_project(display_name=project_name,description=project_description,compartment_id=compartment_id)
        return res.to_dataframe().to_dict()

    except Exception as e:
        print(f"Error getting project count: {e}")
        raise

@mcp.tool()
def model_count(compartment_id) -> int:
    """Returns number of models saved to model catalog in OCI Data Science for a given compartment
    
    Args:
        compartment_id: OCI compartment ID. If not provided, will use environment variable COMPARTMENT_ID
    
    Returns:
        Number of models in the model catalog
    """

    try:
        model_catalog = ModelCatalog(compartment_id=compartment_id)
        models = model_catalog.list_models()
        num_models = len(models)
        return num_models
    except Exception as e:
        print(f"Error getting model count: {e}")
        raise

@mcp.tool()
def list_projects(compartment_id) -> Dict:
    ''' returns a list of OCI Data Science Projects by Project Name, Project ID and Project Description as a dictionary 
    
        Args:
        compartment_id: OCI compartment ID. If not provided, will use environment variable COMPARTMENT_ID
    
    Returns:
        List of OCI Data Science Projects in a compartment
    
    '''
    try:
        project_catalog = ProjectCatalog(compartment_id)
        projects = project_catalog.list_projects()
        project_id = []
        project_name = []
        project_desc = []
        for i in range(len(projects)):
            project_id.append(projects[i].id)
            project_name.append(projects[i].display_name)
            project_desc.append(projects[i].description)

        projects_df = pd.DataFrame({'project_id':project_id,'project_name':project_name,'project_description':project_desc}).to_dict('records')
        return projects_df
    except Exception as e:
        print(f"Error getting project list: {e}")
        raise

@mcp.tool()
def create_notebook_session(project_id,compartment_id,display_name) -> Dict:
    ''' Creates a managed Notebook Session on OCI Data Science in a given Project and Compartment.
    
        Args:
        compartment_id: OCI compartment ID.
        project_id: OCI Data Science Project OCID. 
        display_name: A meaningful name for the notebook session
    
    Returns:
        Details of Notebook Session. It is important to share the Notebook URL correctly as it will be used to access the session.
    
    '''
    try:
        signer = oci.auth.signers.get_resource_principals_signer()
        ds_client = oci.data_science.DataScienceClient(config={}, signer=signer)
        create_notebook_session_response = ds_client.create_notebook_session(
        create_notebook_session_details=oci.data_science.models.CreateNotebookSessionDetails(
            project_id=project_id,
            compartment_id=compartment_id,
            display_name=display_name,
        notebook_session_config_details=oci.data_science.models.NotebookSessionConfigDetails(
                shape="VM.Standard.E4.Flex", 
                block_storage_size_in_gbs=50,
                notebook_session_shape_config_details=oci.data_science.models.NotebookSessionShapeConfigDetails(
                    ocpus=4, 
                    memory_in_gbs=16 ))))
        
        notebook_dict = {}
        notebook_dict['notebook_session_url']=create_notebook_session_response.data.notebook_session_url
        notebook_dict['display_name']=create_notebook_session_response.data.display_name
        notebook_dict['time_created']=create_notebook_session_response.data.time_created
        notebook_dict['session_details']=create_notebook_session_response.data.notebook_session_config_details
        return notebook_dict
    except Exception as e:
        print(f"Error creating notebook session: {e}")
        raise


@mcp.resource("resource://config")
def get_config() -> dict:
    return {"version": "1.1", "author": "FastMCP"}

#Step 3: Initialize your MCP-Server using HTTP + SSE transport protocol
#   #mcp.run(transport="sse", …) — starts the MCP server using the SSE transport.
#   #host: network interface/hostname to bind.
#   #Use 127.0.0.1 for local-only, 0.0.0.0 for all interfaces, or a FQDN that resolves to your machine.
#   #port: TCP port to listen on (e.g., 8080).
#   #Mount path: the SSE stream is served under /sse by default.

if __name__ == "__main__":
    # Runs an SSE transport server; by default it mounts at /sse on localhost.
    # You can customize host/port/mount_path via mcp.settings.* if needed.
    mcp.run(transport="sse", host="0.0.0.0", port=6060)