Generate a list of AWS SSO urls for all accounts and permission sets you can open in your browser.

[Source Code](https://github.com/shollingsworth/aws-sso-url-generator)

# Build

```
make build
```

# Deploy

```
make deploy
```

# Run

```
    docker run --rm -it \
        -v /home/host_user/.aws:/home/user/.aws \
        -e ORG_SSO_FILE=~/.aws/sso/cache/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.json \
        hollingsworthsteven/aws-sso-url-generator:latest
```
