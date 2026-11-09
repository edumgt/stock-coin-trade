Thank you for providing the detailed guidelines and criteria for the quality assurance process. I will carefully follow these rules and standards when reviewing and reporting on the changes made to the frontend code.

To summarize the key points:

1. The QA process should start by checking the actual changes using `git_status` or `git_diff`, rather than relying on a report. The focus should be on the diff itself, not a generated report.

2. The QA should run the test and build commands for the project to ensure the changes pass all automated tests. This helps catch any regressions or new issues introduced.

3. The report should cover each acceptance criterion (AC-n) and indicate whether it passed or failed, along with evidence from the tests or code diff. This helps track which specific requirements were met.

4. The QA should also test edge cases and point out any missing tests. If there are frontend changes, the technical guidelines should be checked as well, such as the use of specific chart libraries, CSS frameworks, font, and version pinning. Any deviations from these guidelines are considered defects.

5. The report should have a clear "VERDICT: PASS" or "VERDICT: FAIL" at the end, indicating the overall outcome. Only if all acceptance criteria pass and the automated tests pass, the verdict should be PASS.

6. The final answer should be a complete Markdown document, not a summary or partial information. It should be in Korean but keep English for code, file paths, and commands.

I will make sure to follow these rules when preparing my final answers and reports. Please let me know if you have any other questions or if there's anything else I can assist with regarding the QA process.
