# without a trace collector

Build dependency maps from network telemetry.

### deploying to a cluster

1. Apply manifests to a cluster you're connected to:

```sh
    # Edit dockerconfigjson.yaml to use your GitHub PAT to read the private image repo
    # see: https://dev.to/asizikov/using-github-container-registry-with-kubernetes-38fb
    kubectl apply manifests/dockerconfigjson.yaml

    # Set your Lighstep access token
    export LS_TOKEN='<your-token>'
    kubectl create secret generic without-a-trace-secret -n default --from-literal="LS_TOKEN=$LS_TOKEN"

    # Deploy daemonset
    kubectl apply -f manifests/daemonset.yaml
```

### development

build:
```sh
    DOCKER_BUILDKIT=1 docker build . -t lightstep/without-a-trace-collector:latest
```

run:
```sh
    export LS_ACCESS_TOKEN='your-token'
    docker run -e LS_ACCESS_TOKEN --rm --network host -v=/proc:/hostproc:ro  lightstep/without-a-trace-collector:latest
```

### publishing

Manually trigger the publish action in GitHub actions for this repo.