import os, json, subprocess; 

repos = json.loads(os.environ["POETRY_REPOS_JSON"]); 
user = os.environ["POETRY_REPOS_USER"]; 
pwd = os.environ["POETRY_REPOS_PASSWORD"]; 
for r in repos: 
    NAME = r["name"] 
    subprocess.run(["poetry", "config", f"repositories.{NAME}", r["url"]], check=True); 
    subprocess.run(["poetry", "config", f"http-basic.{NAME}", user, pwd], check=True)