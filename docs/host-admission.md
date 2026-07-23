# Local k3s GPU Runtime Admission

Ticket 02 is a fail-closed admission procedure for the declared native-Ubuntu
workstation. The checked-in contract and manifests are reviewable on any host,
but only a successful run on the single-node RTX 3080 workstation can produce
passed evidence.

The target operator first runs the bounded cluster checks:

```sh
bin/run-cluster-admission --output /tmp/cluster-results.json
```

After reviewing that output, collect a sanitized Evidence Package outside the
repository:

```sh
bin/collect-host-admission \
  --access-method local-console \
  --cluster-results /tmp/cluster-results.json \
  --infrastructure-revision "$(git rev-parse HEAD)" \
  --output /tmp/host-admission.json
```

The cluster procedure verifies the node label and taint, exactly one
`nvidia.com/gpu`, a digest-pinned CUDA container, an exactly-one-GPU pod, the
non-GPU taint guard, and a bounded unavailable-capacity outcome. It also records
idle and smoke measurements against the checked-in stop limits. The collector
accepts only native amd64 Ubuntu and allowlists reviewable fields, excluding
hostnames, addresses, serials, credentials, and kubeconfig content.

`contracts/host-admission/v1/pending-evidence.template.json` is a pending
template, not execution evidence. Current macOS and hosted CI runs validate only
contracts, manifests, sanitization, and failure behavior. This lab makes no
high-availability, autoscaling, distributed, production-reliability, or SLO
claim.
