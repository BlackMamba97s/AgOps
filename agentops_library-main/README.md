
# How to use private PyPi server

## Add repository to Poetry environment 
 ```bash
poetry config repositories.<CUSTOM-NAME> <URL-TO-REPO>
poetry config http-basic.<CUSTOM-NAME> <USER> <PASS>
```

## Use in Poetry project

Inside the `project.toml`

```txt project.toml
...

[[tool.poetry.source]]
name = "<CUSTOM-NAME>"
url = "<URL-TO-REPO>"

[tool.poetry.dependencies]
examplepacket1 = { version = "0.1.4", source = "<CUSTOM-NAME>" }
examplepacket2 = { version = "1.2.3", source = "<CUSTOM-NAME>" }
other_packet_from_public_repo==2.2.4
...

```