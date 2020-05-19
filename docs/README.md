# Clin user guide
```
~ clin --help
```

- [Core concepts](#core-concepts)
- [Configuration](#configuration)
- [Manifests format](#manifests-format)
- [Applying single manifest](#applying-single-manifest)
- [Batch processing](#batch-processing)
- [Dumping](#dumping)

## Core concepts
**clin** sends http requests to Nakadi to create or update resources. The source
of data for this is yaml manifest file which corresponds to a single Nakadi
resource.

These manifests can be applied:
- directly one by one, see
  [Applying single manifest](#applying-single-manifest).
- in batch by using a "clin file" to roll out whole infrastructure with a single
  command, see [Batch processing](#batch-processing).

`{{TEMPLATE_VARIABLES}}` and `@@@./includes.yaml` , optionally enforced by
[yaml anchors](https://www.google.com/search?q=yaml+anchors) enable expressive
and DRY definition of the Nakadi infrastructure.

For more details see [Manifests format](#manifests-format).

### Dry-run by default
Each command that can possibly change Nakadi resources in NOT performing any
changes by default. To apply actual changes, additional key `-X` or `--execute`
should be specified:
```bash
~ clin apply --env staging event-type.yaml
Will create event type 'derokhin.clin.test'

~ clin apply -X --env staging event-type.yaml
Successfully created event type 'derokhin.clin.test'
```

### No updates if no changes
Clin would not touch something that is not changed:
```bash
~ clin apply --env staging event-type.yaml
Up to date: event type 'derokhin.clin.test'
```
With dry run and [batch processing](#batch-processing) this can be used to see
if actual state is differs from the set of manifests in your codebase

### OAuth support
Clin supports authorization for all operations using OAuth. To enable OAuth,
retrieve a valid token using your preferred method and pass it to clin using
`-t` or `--token`:
```bash
~ clin apply --env staging --token $TOKEN event-type.yaml
Will create event type 'derokhin.clin.test'
```

### Environment aware
Clin supports multiple environments that have to be configured and specified on
every command.

## Configuration
Clin uses configuration using a yaml file located either in the command's
working dir (usually the project root) or in the user's home directory.
The configuration file in the working dir takes precedence, but note that the
configuration is **not** hierarchical, i.e. a configuration file will completly
override/replace another.

```yaml
environments:
    staging:
        nakadi_url: https://nakadi-staging.local
    production:
        nakadi_url: https://nakadi-production.local
```

## Manifests format
```yaml
kind: event-type
spec: #...
```
Kind defines the type of Nakadi resource. Currently supported:
- `event-type`
- `subscription`

`spec` defines the resource's properties. Please refer examples
[/docs/examples/single](/docs/examples/single) for the details of the
properties.

### Template variables
Manifest yaml can include template variables in double curly braces (`{{VAR}}`)
which will be substituted from the external context.

In case of [applying single manifest](#applying-single-manifest)) this context
is taken from
environment variables of your shell. I.e.:
```yaml
#...
  auth:
    users:
      admins:
        - {{USER}}
#...
```
when applying it in bash, the current user will be the admin of the event type
or subscription.


In case of batch processing (see [Batch processing](#batch-processing)), context
is defined for each of the processes in the env section. For instance, given one
of manifests in `./apply` folder:
```yaml
kind: event-type
spec:
  name: my-event-type{{POSTFIX}}
#...
```

and clin file `./my-service.clin.yaml`:
```yaml
process:
  - id: Production
    target: production
    paths: ["./apply"]
    env:
      POSTFIX: ""

  - id: Production copy for partners
    target: production
    paths: ["./apply"]
    env:
      POSTFIX: "_copy"
```

Variables can be either scalar types and then they can be substituted everywhere
(like in the example above, `POSTFIX` included into the string. Or they can be
compound types (objects or array) and they can be included only entirely:

```yaml
process:
  - id: Production
    #...
    env:
      SCHEMA:
        type: object
        properties:
          important_key:
            type: string
        required:
          - important_key
```

```yaml
#...
  schema:
    compatibility: compatible
    jsonSchema: {{SCHEMA}}
#...
```

If a variable, found in manifest is not defined in the context – the process
will be interrupted.

### Includes
Manifest can include other yaml file

```yaml
#...
  schema:
    compatibility: compatible
    jsonSchema: @@@./schema.yaml
#...
```
content of `schema.yaml` will be included as a value of field `jsonSchema`.

There are no limitations on the depth of inclusion, i.e. `schema.yaml` itself
can contain includes of some parts from other files. Cyclic references are not
permitted

First includes resolved and then variables are processed, which means:
- included files can contain variables which will be processed from same context
- include reference can NOT contain variable, following is invalid:
  ```yaml
    jsonSchema: @@@./{{CLIENT}}/schema.yaml
  ```

## Applying single manifest
Use command `apply` to create or update a single event type or subscription.
Your shell environment variables will be used as a context to resolve template
variables. Natural limitation here – variables can be only strings.

## Batch processing
To apply multiple Nakadi resources, a clin file is needed (please find full
example in [/docs/examples/batch](/docs/examples/batch)). This file defines a
list of processes to be executed.
```yaml
process:
  - id: Staging
    target: staging
    paths: [./apply]
    env:
      TEAM: "avengers"
      ADMINS: @@@./users/avengers.users.yaml
```

Where:
- `id` - just a name, string with no additional constraints
- `target` - the environment this step is executed against. The environment must
  be present in the [configuration](#configuration) file.
- `paths` - array of paths to be processed. Each path will be scanned (non
  recursively) for yaml files (`*.yaml` or `*.yml`). Each found yaml file is
  considered to be a resource manifest.
- `env` - object with key-value pairs used for processing template variables in
  the discovered manifests.

Include logic applies while processing the clin file (with one
[minor restriction](clin/issues/#28)).

Template variable if exists in clin file will be processed with shell
environment variables

Sequence of processing:
- collect all manifests from all processes (with resolving includes and template
  variables)
- process all event types
- process all subscriptions

## Dumping
Manifest for existent event type can be created by using the `dump` command. It
will be printed to stdout
