# Technical Rules

## Code Blocks
ALWAYS specify the programming language in markdown code blocks.
Example:
```python
print("Hello")
```

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
