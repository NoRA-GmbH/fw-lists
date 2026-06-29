# OpenAI ChatGPT Connectors List Builder

Generates firewall lists from the official OpenAI ChatGPT connector egress IP ranges.

Source:

```text
https://openai.com/chatgpt-connectors.json
```

## Usage

```bash
python scripts/openai/get-openai-chatgpt-connectors.py --output-dir lists/openai
```

## Output Files

- `openai_chatgpt_connectors_ipv4.txt` - IPv4 CIDR list
- `openai_chatgpt_connectors_ipv6.txt` - IPv6 CIDR list, empty when OpenAI publishes no IPv6 connector ranges

Both lists can be used with tools such as BunkerWeb `WHITELIST_IP_URLS`.
