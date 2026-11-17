# Client Audit Lite

A free Claude plugin that audits a web page for SEO and AI-search visibility from measured facts and writes a scored report in Arabic or English.

The plugin lives in [`client-audit-lite/`](client-audit-lite/); its own README explains what it does, what it measures and what it does not.

## Install

Requires Claude Code 2.1.275 or later.

```
/plugin install client-audit-lite --marketplace reemalfadly/client-audit-lite
```

## Run the tests

```
python -m pip install -r client-audit-lite/mcp/requirements.txt
python -m unittest discover -s tests
```

The tests use small local test servers.

## License

MIT. See [`client-audit-lite/LICENSE`](client-audit-lite/LICENSE).
