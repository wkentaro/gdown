# Issue and Pull Request Labels

## Issues

Every triaged issue carries exactly one `type:` label and one triage label. An issue with no triage label is fresh work for the agent to route; `needs-triage` is reserved for a decision only the maintainer can make.

| Type label | Meaning |
| --------------- | --------------------------------------------------- |
| `type: bug` | Reporting a defect to fix |
| `type: feature` | Requesting a new capability or improvement |
| `type: task` | Maintenance, refactor, documentation, or other work |

| Triage label | Meaning |
| ----------------- | -------------------------------------------- |
| `needs-triage` | Maintainer needs to evaluate the issue |
| `needs-info` | Waiting on the reporter for more information |
| `ready-for-agent` | Fully specified and ready for an AFK agent |
| `ready-for-human` | Requires human implementation |
| `wontfix` | Will not be actioned |

## Pull requests

A draft pull request is still being built. A non-draft pull request with no agent verdict is ready for the agent to finalize. `needs-info` is shared with issues and means the pull request is waiting on an outside human.

The agent records exactly one terminal verdict:

| Agent verdict | Meaning |
| ------------------ | ------------------------------------------------------------- |
| `recommend-merge` | Finalized and endorsed for maintainer review and merge |
| `recommend-close` | Recommended for maintainer review and closure |
| `recommend-triage` | Technically sound; the maintainer must decide product or scope |

`maintainer-approved` records an explicit maintainer decision to merge after required checks pass. An agent applies it only on explicit maintainer direction and never infers it from CI, mergeability, or an agent verdict. It may coexist with one agent verdict because the labels record different authorities.

Verdicts record decisions; they do not merge or close pull requests. A new commit makes every applicable verdict stale: remove it and have the same authority review the new diff before renewing it.
