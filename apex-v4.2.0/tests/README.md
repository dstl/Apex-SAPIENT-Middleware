# Elastic Search Testing Environment

An elastic search environment can be spun up with docker compose. It relies on a few variables
defined in `./tests/.env`.

The docker compose file, `./tests/docker-compose.yml`, will first spin up a container that sets up
the requisite security credentials. A certificate will be created in `${CREDENTIALS_DIR}/es-ca.crt`
for later use with elastic search. Containers for an elastic search instance and Kibana instance are
also defined in turn.

Spin up the environment with:

```bash
cd tests
docker compose up # add '-d' to detach
```

And spin it down with:

```bash
docker compose down # add '-v' to delete volumes as well
```

Test elastic search is up with:

```bash
> curl --cacert "$CREDENTIALS_DIR/ca.crt" -u "elastic:$ELASTIC_PASSWORD" https://localhost:$ES_PORT
{
  "name" : "es01",
  "cluster_name" : "apex-es",
  "cluster_uuid" : "SDEpd46tRwSGbj_30nttaQ",
  "version" : {
    "number" : "8.7.1",
    "build_flavor" : "default",
    "build_type" : "docker",
    "build_hash" : "f229ed3f893a515d590d0f39b05f68913e2d9b53",
    "build_date" : "2023-04-27T04:33:42.127815583Z",
    "build_snapshot" : false,
    "lucene_version" : "9.5.0",
    "minimum_wire_compatibility_version" : "7.17.0",
    "minimum_index_compatibility_version" : "7.0.0"
  },
  "tagline" : "You Know, for Search"
}
```

An bring up Kibana on `https://localhost:${KIBANA_PORT}`.

It is also possible to run the tests with:

```bash
docker compose --file docker-compose.yml --file docker-compose.test.yml run unit-tests
```

This will output a file `pytest_report.xml` to the test directory.

# Load Testing

A simple load-testing script is available by running from the root of the repo:

```bash
python -m tests.loadtesting registration --help
```

Currently, it tests registration and status reports by child nodes to a single fusion node. It
tracks the time for the registration message to come through, for the registration acknowledgment to
come back, and the time for the status reports to come through as well. The output takes the form of
simple statistics. Optionally the response times can be plotted to the command-line, though that
will require a Unicode-enabled terminal emulator and font.
