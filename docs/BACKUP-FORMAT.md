# Local backup format v1

UTF-8 JSON, at most 16 MiB: `{"app":"DizyTV","version":1,"data":{...}}`.

`data` contains `settings`, `channels`, `favourites`, `mappings` and `jobs`. Channels use stable `id`, `name`, `group`, `tvg_id`, `stream` fields. Programmes and timers use integer Unix seconds in UTC. Jobs contain `id`, `channel_id`, `title`, `start`, `end`, `status` and optional recording results.

Local video files, downloaded guide cache, credentials, file paths and Android storage grants are excluded. A restore is replacement of these preferences after confirmation, validated completely before writing. All nonterminal imported jobs become `paused`; finished/expired jobs retain history or become `missed`. Recording destinations must be chosen again. Rearming a timer checks the destination and conflicts. A backup made on one platform can restore favourites and preferences on another.

`settings.timezone` is `auto` or an IANA identifier. `epg_offset_minutes` adjusts newly imported programme timestamps only. An accepted timer is never rewritten when the display timezone, EPG feed or offset changes.
