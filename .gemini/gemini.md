# Gemini Project Directives

## Code Execution and Modification Protocols
- **Script Execution Hazard:** NEVER pipe multi-line scripts, complex regex, or scripts containing raw quotes/newlines directly through `powershell -Command` or via CLI wrappers. This leads to severe escaping and syntax corruption.
- **File Writing Protocol:** ALWAYS use the native `write_file` tool to save scripts (Python, JS, etc.) to the disk before executing them. 
- **HTML/DOM Manipulation:** NEVER use Regular Expressions to parse or extract nested HTML blocks (like `<div>` tags). Always use robust parsers (like BeautifulSoup or Python's `html.parser`) to modify DOM structures, or utilize surgical block replacements that do not risk orphaned tags.
- **Validation Before Deployment:** Any structural changes to HTML or UI must be locally validated (using an HTML parser or an E2E tool like Playwright) to ensure perfectly matched tags before committing or pushing code.
