# Set up Venice in your agent

To set up Venice, paste this message into your agent. Everything after it is for the agent.

```text
Set up Venice AI for me so I can make images, video, music and speech from here.
1. Install the Venice skills for all my projects: npx -y --ignore-scripts skills@1.7.6 add veniceai/skills -g -y -a <your agent: claude-code, codex, cursor, opencode or hermes-agent>
2. Add the Venice MCP server to your user-level MCP config, not a project file: command npx, args -y --ignore-scripts @veniceai/mcp-server@0.3.1, env VENICE_API_KEY set to the placeholder <VENICE_API_KEY>.
3. Tell me which file to put my Venice INFERENCE key in, from https://venice.ai/settings/api, ideally with a spend limit, and I'll replace the placeholder myself. Only ask me to paste the key here if I'd rather; then write it into that file and nowhere else. Never print it or commit it.
4. Once I've added the key, and after a restart if the Venice tools aren't loaded, make one test image with venice_image_generate and model z-image-turbo ($0.01), and show it to me.
For the exact steps in your agent, read SETUP.md in the veniceai/skills repository on GitHub.
```

You are an AI agent, and the user asked you to set up Venice AI. Follow these steps in order. Afterwards the user can make images, video, music and speech from the chat, and you have the Venice skills, which tell you how to use the Venice API well.

## Rules

- Use the commands on this page as written, at the versions shown, and keep `--ignore-scripts`.
- The API key is a secret, so keep it out of the chat. Write the config with `<VENICE_API_KEY>` in its place and have the user put their key in that file. Take the key in the chat only if the user prefers that, and then write it into that file and nowhere else.
- Use an INFERENCE key, never an ADMIN key. Keep it only in the user-level config from step 2: never write it into a file inside a git repository, show it back to the user, or commit it.
- Generating media costs money. Make only the test image in step 4 without asking first.

## 1. Install the skills

```bash
npx -y --ignore-scripts skills@1.7.6 add veniceai/skills -g -y -a <agent>
```

Replace `<agent>` with your own name in the `skills` CLI: `claude-code`, `codex`, `cursor`, `opencode` or `hermes-agent`. This installs every Venice skill for all of the user's projects, into your skills folder. It needs Node.js 22.20 or later. Keep the pinned version, and keep `--ignore-scripts` before the package name, where `npx` reads it. Without `-a`, the CLI also tries agents that can't take a global install and reports them as failures.

Other ways, if that one doesn't fit:

- **Claude Code:** the Venice plugin installs the skills and the MCP server together, and asks for the key in a secure prompt, so the key never enters the chat. Ask the user to run `/plugin marketplace add veniceai/skills` and then `/plugin install venice@venice` in Claude Code, then go to step 4.
- **Codex:** run `codex plugin marketplace add veniceai/skills`, then `codex plugin add venice@venice`.
- **Without Node.js 22:** clone the `veniceai/skills` repository from GitHub and run its `link-skills` script with `--agent` set to `claude-code`, `codex`, `cursor`, `opencode` or `hermes-agent`.

## 2. Add the Venice MCP server

Add the server at user level, so it works in every project and the key stays out of project files. Use `<VENICE_API_KEY>` as the key for now; step 3 fills it in. The server needs Node.js 20 or later.

| Agent | How | Config file |
|---|---|---|
| Claude Code | `claude mcp add venice --scope user --env 'VENICE_API_KEY=<VENICE_API_KEY>' -- npx -y --ignore-scripts @veniceai/mcp-server@0.3.1` | `~/.claude.json` |
| Codex | `codex mcp add venice --env 'VENICE_API_KEY=<VENICE_API_KEY>' -- npx -y --ignore-scripts @veniceai/mcp-server@0.3.1` | `~/.codex/config.toml` |
| OpenCode | `opencode mcp add venice --global --env 'VENICE_API_KEY=<VENICE_API_KEY>' -- npx -y --ignore-scripts @veniceai/mcp-server@0.3.1`. Older versions reject `--global` and already write to the global config, so drop the flag there. | `~/.config/opencode/opencode.json` or `opencode.jsonc` |
| Cursor | Add the `venice` entry below to `mcpServers`, and keep the servers already there. | `~/.cursor/mcp.json` |
| Hermes Agent | Add the YAML entry below under `mcp_servers`. If the tools don't appear, ask the user to run `/reload-mcp`. | `~/.hermes/config.yaml` |
| Any other MCP client | Add the `venice` entry below. | The client's user-level MCP config |

Keep the quotes around `VENICE_API_KEY=<VENICE_API_KEY>` in those commands: without them, the shell reads `<` and `>` as redirections.

```json
{
  "mcpServers": {
    "venice": {
      "command": "npx",
      "args": ["-y", "--ignore-scripts", "@veniceai/mcp-server@0.3.1"],
      "env": { "VENICE_API_KEY": "<VENICE_API_KEY>" }
    }
  }
}
```

```yaml
mcp_servers:
  venice:
    command: npx
    args: ["-y", "--ignore-scripts", "@veniceai/mcp-server@0.3.1"]
    env:
      VENICE_API_KEY: "<VENICE_API_KEY>"
```

## 3. Have the user add their key

Tell the user which file you wrote, and ask them to replace `<VENICE_API_KEY>` there with an INFERENCE key from https://venice.ai/settings/api, ideally one with a spend limit. Suggest a daily or monthly cap under **Spend limits** in the key form. If they want chat kept private, suggest **Model privacy** set to *Private text, Anonymous otherwise*, which still allows image, video and audio models; *Private models only* rejects anonymized models, which include most image and video models and every music model. If they'd rather paste the key into the chat, write it into that file yourself, and nowhere else.

## 4. Check that it works

A new MCP server usually loads in a new session. Once the user has added the key, ask them to restart you if the `venice_*` tools aren't available yet, then continue.

Call `venice_image_generate` with `model: "z-image-turbo"`, which costs $0.01, and a short prompt, and show the image to the user.

If it fails:

- **401, or a 402 that says to set `VENICE_API_KEY`:** the key is wrong, or the file still holds a placeholder such as `<VENICE_API_KEY>` or `${VENICE_API_KEY}`. Check the `env` value.
- **402 about credit or a spend limit:** the account is out of credit, or the key reached its spend limit. The user can add credit or raise the limit at https://venice.ai/settings/api.
- **The server doesn't start:** check that `node --version` is 20 or later.
- **No `venice_*` tools after a restart:** check the config entry for typos.

## 5. Tell the user

Say that Venice is ready, without explaining file paths, and suggest a few things to try:

- "Make a 5-second video of a paper boat sailing down a rainy street."
- "Turn this product photo into a studio shot and a lifestyle shot."
- "Write and produce a 30-second lo-fi jingle."
- "Make a YouTube thumbnail for this video."
- "Turn this document into a one-minute narrated explainer."
