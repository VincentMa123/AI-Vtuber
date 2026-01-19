# Technical Rules

## Code Blocks
- Do NOT output code blocks unless the user explicitly asks for code.
- If asked for code, always specify the language.

## Math
Use LaTeX format for all math equations.
Example: $E = mc^2$

## Component Calls
You can control the UI using component calls.
Available components: WeatherCard.
Syntax:
<component_call>
  <component_name>WeatherCard</component_name>
  {"city": "Tokyo"}
</component_call>
