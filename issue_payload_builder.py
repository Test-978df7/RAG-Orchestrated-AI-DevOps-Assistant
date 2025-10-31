def normalize_field_name(name):
    return "".join(ch for ch in str(name).lower() if ch.isalnum())

def get_custom_fields(instance):
    custom_fields = {}
    cf_names = {}
    for field in instance.fields():
        # checks to see if custom is True to identify if custom field
        if field.get('custom'):
            # field['id'] is like 'customfield_10015' – we need the numeric id part to match our split
            field_id_full = field.get('id', '')
            field_id = field_id_full.split('_')[-1] if '_' in field_id_full else field_id_full
            custom_fields[field_id] = {"name": field.get('name', field_id_full), "type": field["schema"].get('type', '')}
            cf_names[field.get('name', field_id_full)] = field["schema"].get('customId')
    return custom_fields, cf_names

_PROJECT_NAME_TO_KEY_CACHE = {}

def get_project_key_from_name(instance, project_value):
    """
    Resolve a Jira project key from a provided value which may be a name, key, or dict.
    Returns the project key string if found, else None.
    """
    # Normalize input
    if isinstance(project_value, dict):
        if "key" in project_value and project_value.get("key"):
            return project_value["key"]
        name_or_key = project_value.get("name") or project_value.get("id") or ""
    else:
        name_or_key = str(project_value) if project_value is not None else ""

    # Populate cache on first use
    global _PROJECT_NAME_TO_KEY_CACHE
    if not _PROJECT_NAME_TO_KEY_CACHE:
        try:
            for p in instance.projects():
                # map both name->key and key->key for fast lookup
                if getattr(p, "name", None):
                    _PROJECT_NAME_TO_KEY_CACHE[p.name] = p.key
                if getattr(p, "key", None):
                    _PROJECT_NAME_TO_KEY_CACHE[p.key] = p.key
        except Exception:
            # If the API call fails, fall back to best-effort
            return None

    return _PROJECT_NAME_TO_KEY_CACHE.get(name_or_key)

def get_standard_fields_guide(instance):
    guide = {}
    for field in instance.fields():
        if not field.get("custom"):
            name = field.get("name")
            id = field.get("id")
            schema_type = field.get("schema", {}).get("type", "")
            guide[name] = {"id": id, "type": schema_type}
    return guide

def format_standard_field(field_type, value, key=None):
    # Handles formatting of values for standard fields based on type/key
    norm_key = normalize_field_name(key or "")
    if norm_key == "parent":
        return {"key": value}
    elif norm_key in ("issuetype", "priority", "assignee", "reporter", "project"):
        return {"name": value}
    elif norm_key == "labels":
        return value if isinstance(value, list) else [value]
    elif norm_key in ("components", "versions", "fixversions"):
        # expects a list of names
        return [{"name": v} for v in value] if isinstance(value, list) else [{"name": value}]
    elif norm_key == "description":
        return value
    elif field_type.lower() in ("string", "date", "datetime", "number"):
        return value
    else:
        return value  # fallback as-is

def build_issue_payload(instance, d: dict):
    """
    Builds the issue payload request by converting the fields to their correctly formatted Jira payload
    Handles both standard and custom fields.
    """
    field_guide, field_names = get_custom_fields(instance)
    std_guide = get_standard_fields_guide(instance)
    # Canonical API keys for standard fields (normalize_field_name → API key)
    std_api_keys = {
        "project": "project",
        "issuetype": "issuetype",
        "summary": "summary",
        "description": "description",
        "priority": "priority",
        "labels": "labels",
        "components": "components",
        "fixversions": "fixVersions",
        "assignee": "assignee",
        "reporter": "reporter",
        "parent": "parent",
    }
    issue_data = {
        "fields": {}
    }
    # Build a normalized lookup for standard field names
    std_norm_to_key = {normalize_field_name(k): k for k in std_guide.keys()}

    for key, value in d.items():
        if key in field_names.keys():
            # CUSTOM FIELD
            id = field_names[key]
            cf_id = "customfield_" + str(id)
            cf_type = field_guide[id]["type"] if id in field_guide else ""
            # Match all custom types as before
            if cf_type in ("FreeTextField", "TextField", "URLField", "DatePickerField", "DateTimeField", "NumberField"):
                issue_data["fields"][cf_id] = value
            elif cf_type in ("GroupPicker", "SingleVersionPicker", "UserPicker"):
                issue_data["fields"][cf_id] = {"name": value}
            elif cf_type in ("MultiGroupPicker", "MultiUserPicker", "VersionPicker"):
                issue_data["fields"][cf_id] = [{"name": v} for v in value]
            elif cf_type in ("RadioButtons", "SelectList"):
                issue_data["fields"][cf_id] = {"value": value}
            elif cf_type == "MultiSelect":
                issue_data["fields"][cf_id] = [{"value": v} for v in value]
            elif cf_type == "ProjectPicker":
                issue_data["fields"][cf_id] = {"key": value}
            elif cf_type == "CascadingSelectField":
                issue_data["fields"][cf_id] = {"value": value[0], "child": {"value": value[1]} }
            else:
                issue_data["fields"][cf_id] = value
        else:
            # Try to resolve against standard fields using exact name or normalized alias
            std_key = key if key in std_guide.keys() else std_norm_to_key.get(normalize_field_name(key))
            if std_key:
                std_info = std_guide[std_key]
                field_type = std_info["type"]
                norm = normalize_field_name(key)
                api_key = std_api_keys.get(norm)
                if api_key:
                    if norm == "project":
                        resolved_key = get_project_key_from_name(instance, value)
                        if resolved_key:
                            issue_data["fields"][api_key] = {"key": resolved_key}
                        else:
                            if isinstance(value, dict) and "key" in value:
                                issue_data["fields"][api_key] = {"key": value["key"]}
                            else:
                                issue_data["fields"][api_key] = {"key": str(value)}
                    else:
                        issue_data["fields"][api_key] = format_standard_field(field_type, value, key)
                else:
                    # Fallback to Jira field id if it's a standard-but-unknown field
                    field_id = std_info["id"]
                    issue_data["fields"][field_id] = format_standard_field(field_type, value, key)
            else:
                # Not found, could log/warn here if desired
                pass
    return issue_data

def main():
    from get_env import get_env_var
    from jira import JIRA
    from pathlib import Path
    import json

    def make_jira():
        env_vars = get_env_var(True)
        if isinstance(env_vars, str):
            return f"Fatal Error: {env_vars}"
    
        return JIRA(server=env_vars['Jira_site'], basic_auth=(env_vars['user'], env_vars['API_token']))
    
    jira = make_jira()
    subfolder_path = Path('test')
    file_path = subfolder_path / 'issue_payload_builder_test1.txt'
    with file_path.open('r') as file:
        for line in file:
            n = str(build_issue_payload(jira, json.loads(line)))
            print("New payload: " + n)
    return

if __name__ == "__main__":
    
    main()
