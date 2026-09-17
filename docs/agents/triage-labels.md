# Issue and Pull Request Labels

A triaged issue carries exactly one `type:` label and one triage state. An
unlabeled issue is untriaged; `needs-triage` means it is under evaluation.

A non-draft pull request with no verdict is ready for the agent to finalize.
The draft flag is the still-being-built state; there is no draft label.

The agent emits at most one `recommend-*` verdict per pull-request head.
`recommend-revise` hands the pull request back to its author; the other three
hand it to the maintainer. Verdicts are recommendations: the agent never merges
or closes.

Never rename `recommend-merge` to `ready-to-merge`; merge bots watch that
string. `maintainer-approved` is set only on explicit maintainer direction and
may coexist with a `recommend-*` label.

A new push makes any verdict stale. The authority that set it clears and
renews it.

## `/triage` role mapping

| Role | Issue label | Pull-request label |
| --- | --- | --- |
| `bug` | `type:bug` | — |
| `enhancement` | `type:feature` | — |
| `needs-triage` | `needs-triage` | `recommend-triage` |
| `needs-info` | `needs-info` | `recommend-revise` |
| `ready-for-agent` | `ready-for-agent` | — |
| `ready-for-human` | `ready-for-human` | `recommend-merge` |
| `wontfix` | `wontfix` | `recommend-close` |

Maintenance, refactor, documentation, and other work use `type:task`.

## Pull-request verdicts

| Label | Meaning |
| --- | --- |
| `recommend-merge` | Agent finalized and endorses it: review and merge |
| `recommend-close` | Agent recommends closing: review or close |
| `recommend-triage` | Code is sound; merge or close is a product call |
| `recommend-revise` | Review found defects or questions; author must revise and push |
| `maintainer-approved` | Maintainer reviewed this head and approves merging after required checks pass |

The agent never applies `maintainer-approved` based on CI, mergeability, or an
agent verdict. It records a separate maintainer decision and may coexist with
one agent verdict.

## Issue triage states

| Label | Meaning |
| --- | --- |
| `needs-triage` | Under evaluation, not yet routed |
| `needs-info` | Waiting on reporter for more information |
| `ready-for-agent` | Fully specified, ready for an AFK agent |
| `ready-for-human` | Requires human implementation |
| `wontfix` | Will not be actioned |
