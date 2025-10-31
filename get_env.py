from pathlib import Path
import logging, os
from dotenv import load_dotenv, set_key
from mcp.server.fastmcp import FastMCP

load_dotenv()
mcp = FastMCP("jira_sentiment")

def get_env_var(from_mcp: bool = False):
    """ Grabs the API token and the Jira site, reqeusts it if it does not exist. """
    # Checks to see if an API token exists in the .env. If not, first checks for a .env and creates it, then requests the email address and API token to store. Skips if from MCP
    env_path = Path('.') / '.env'
    env_path.touch(exist_ok=True)

    # Prefer explicit JIRA-specific variable names; fall back for backwards compatibility
    jira_email = os.getenv("JIRA_EMAIL") or os.getenv("JIRA_USER_EMAIL") or os.getenv("USER")
    api_token = os.getenv("API_TOKEN")
    jira_site = os.getenv("JIRA_SITE")

    if (not jira_email or not api_token) and from_mcp:
        return ("API credentials not set. Please run a setup step to set JIRA_EMAIL and API_TOKEN in .env.")

    if not api_token and not from_mcp:
        user_input = input(f"Please provide the user's Jira email address: ")
        token_input = input(f"""
            Please provide the API Token for user {user_input}. Visit https://id.atlassian.com/manage-profile/security/api-tokens to create a token. 
            Ensure the scoped token has Jira access and the following classic scopes:
            read:jira-work 
            write:jira-work

        """)
        set_key(env_path, "JIRA_EMAIL", user_input)
        set_key(env_path, "API_TOKEN", token_input)
        jira_email, api_token = user_input, token_input

    if not jira_site and from_mcp:
        return ("JIRA site missing. Please set JIRA_SITE in .env (e.g., https://yourorg.atlassian.net).")

    if not jira_site and not from_mcp:
        site_input = input("Please provide the Jira site (e.g., https://yourorg.atlassian.net): ")
        set_key(env_path, "JIRA_SITE", site_input)
        jira_site = site_input

    return {
        'user': jira_email,
        'API_token': api_token,
        'Jira_site': jira_site
    }