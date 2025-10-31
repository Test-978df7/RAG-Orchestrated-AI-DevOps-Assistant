### Jira MCP Server

This is a MCP server that gives AI such as Claude Desktop tools to search for and create issues in a Jira site. You will need to provide the following .env variables:

- JIRA_SITE: the jira site you want to connect to
- JIRA_EMAIL: the user name associated with the API token
- API_TOKEN: the API token for the user, with classic read:jira-work and write:jira-work scopes

### To install

- run install.sh
- In Claude desktop, go to Your Profile > Settings > Developer > Edit Config
- edit claude_desktop_config.json
- Add the Jira MCP server to the config file. See https://modelcontextprotocol.io/docs/develop/connect-local-servers for more details

