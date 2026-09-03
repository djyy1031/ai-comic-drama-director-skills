---
name: create-visual-assets
description: Create original raster images from text with an available MCP image-generation capability. Use when a user asks to generate, illustrate, render, visualize, or produce a new bitmap visual, concept image, background, mockup, poster, social image, texture, or other image asset. Do not use for editing an existing image or generating variations until an available tool explicitly supports those operations.
metadata:
  short-description: 通过可用生图能力生成并展示图片资产
  version: "1.0.0"
---

# 中转站生图

Use any available MCP tool whose schema and description indicate text-to-image generation and whose result supports MCP image content. Discover the capability at runtime; do not depend on a particular server or tool namespace.

## Workflow

1. Extract the subject, purpose, composition, style, lighting, palette, aspect ratio, text requirements, background, and output constraints from the request.
2. Ask a concise question only when a missing choice would materially change the result. Otherwise choose sensible visual defaults.
3. Select an available text-to-image MCP tool by capability and inspect its current input schema. Do not infer parameters from an old invocation or from a fixed server name.
4. Normalize the request using the rules below, then map only values accepted by the current schema.
5. Convert the request into one production-ready prompt. Preserve requested wording exactly when the image must contain text. Add concrete visual details, remove duplicated or contradictory instructions, and do not introduce brands, people, or claims the user did not request.
6. Preflight the complete argument set. Prefer one image unless the user explicitly asks for multiple. Do not silently lower quality, change format, or alter the requested aspect ratio to avoid a slow call. Prefer a capable tool that saves generated images and enforces explicit dimensions or their exact aspect ratio locally.
7. Call the generation tool exactly once. Image generation can incur cost and is non-idempotent. Never retry automatically after any timeout, connection loss, HTTP 5xx response, or other ambiguous failure.
8. Confirm that the result contains standard MCP image content. Read the returned saved-file path and requested/source/final dimensions when the tool provides them.
9. In the final response, render every saved image with Markdown using its absolute path. On Windows, change path separators to forward slashes and wrap the destination in angle brackets so spaces remain valid, for example `![Generated image](<C:/Users/name/Pictures/AI Studio/image.png>)`. Do not merely claim that an image was displayed. If the tool provides only inline image content and no saved path, explain that the final response cannot reliably re-embed it instead of inventing a path.

## Parameter Normalization

- **Model:** Pass an explicit canonical image-model name unchanged. Normalize `image2`, `GPT Image 2`, and `gpt_image_2` to `gpt-image-2`; apply the same pattern to `gpt-image-1` and `gpt-image-1.5`. If an explicitly required model cannot be mapped confidently, stop and ask instead of guessing. If the user did not choose a model, do not send the `model` parameter. Prefer a tool that advertises automatic highest-version image-model selection, and let that tool resolve the latest stable model. Never inject `gpt-image-1` or another remembered default merely because it was used in an earlier task.
- **Size:** Normalize `1024*1024`, `1024×1024`, uppercase `X`, and surrounding spaces to `1024x1024`. When the user gives only an aspect ratio, choose a schema-supported size with that orientation; if none is exposed, use `auto` and include the ratio in the prompt. Treat an explicit size as strict output intent. Inspect returned final dimensions: they must equal the request when the source is large enough; otherwise they must preserve the exact reduced width:height ratio without upscaling. Never claim requested pixels when the returned metadata reports different final pixels.
- **Quality:** Map only explicit `low`, `medium`, `high`, or `auto` concepts supported by the schema. Do not translate vague words such as "good" into a costly setting when the choice materially affects cost.
- **Format and background:** Normalize JPG to JPEG only when the schema uses `jpeg`. Transparent output requires PNG or WebP; when transparent JPEG is requested, ask which constraint to preserve instead of sending an invalid combination.
- **Count:** Default to one. Never turn requested alternatives, panels, or views inside a single composition into multiple billed images unless the user explicitly requests multiple outputs.

## Prompt Construction

Write prompts in a direct visual order:

`subject and action; environment; composition and camera; medium or style; lighting and palette; important details; exclusions; output intent`

Keep negative constraints specific. Use phrases such as `no visible text`, `transparent background`, or `single centered object` only when relevant. Do not silently replace the user's artistic direction with a generic style.

When the request has explicit dimensions, state the reduced aspect ratio in the prompt and keep essential subjects inside a centered crop-safe composition. The image tool may need to center-crop an upstream result to enforce the ratio.

## Capability Boundaries

- If no suitable image-generation MCP tool is available, stop and state that an image-capable MCP server must be configured. Do not substitute source code, SVG, or ASCII art unless the user asks for it.
- Do not call edit or variation tools for a generation request.
- Do not claim that an inline image was saved to disk.
- Do not say an image is visible unless the final response actually contains a Markdown image referencing a returned saved path.
- Do not expose credentials, gateway URLs, or provider internals in the response.
- Treat content policy or upstream rejection as final for that call; report it without attempting prompt evasion.

## Failure Handling

- **Local validation or HTTP 400/422:** Identify the rejected field and show the corrected canonical value. Do not issue a second generation in the same turn unless the user explicitly asks.
- **HTTP 401:** Report that the image capability's credential is invalid or expired. Do not reveal it.
- **HTTP 403:** Report that image generation is disabled or denied for the configured group/account.
- **HTTP 429:** Report rate limiting and any server-provided wait time. Do not retry automatically.
- **Timeout, connection loss, HTTP 408, or HTTP 5xx:** Treat the outcome as unknown because the upstream may still have generated and billed the image. Do not call again. Tell the user to check the gateway usage record before choosing whether to retry. A repeated 504 at a fixed duration indicates a gateway or reverse-proxy timeout, not a prompt-validation problem.
- **Invalid or missing image content:** Report that the upstream response could not be converted to MCP image content. Do not invent a successful result or file path.
