## Welcome to My GitHub Portfolio

## About Me

Hello! I'm Ryan, a Software Developer with a passion for automation and system efficiency. I enjoy continuously learning new skills and developing tools that help end users without being intrusive. Welcome to my GitHub portfolio, where I showcase my automations written in Python for efficient render farm operations.

**Render-Farm-Automations** contains everything I independently developed during my time as a Render Wrangler.

## CRONS

These "Crons" were run at set times at two different geographical locations to perform regular, daily render farm functions, primarily regarding setup for operations during and outside work hours. They would run different functions depending on the location, calling functions from a custom "CronLibrary."

## EVENTS

These files handled executing commands on Event Callbacks within AWS Thinkbox's Deadline. For example, `OnJobSubmission` is called when a job is submitted to the farm.

Some more complex events have multiple callbacks. For example, `SimsSplitModify.py` has five different callbacks to handle jobs that reached various states.

All these files import and use the "DeadlineToolbox," a file I created containing regularly used custom functions.

## Other Files:

- **TheBigRedButton and BigRedButtonUI:** Created for emergency situations to quickly allocate the entire farm to a single type of job.
- **CheckLoggedInUsers:** This script identifies any user who hasn't logged out by 21:00, then emails the list to relevant stakeholders. It also creates a CSV of the day's offenders for logging purposes. This tool maximises machine availability across the company to make the best use of valuable out-of-hours render time.
- **CopyJobBatchNames:** A simple tool to copy the names of highlighted jobs, streamlining information relay to production staff.
- **DeadlineToolbox:** A comprehensive library of regularly used custom functions, invaluable for creating automation scripts efficiently.
- **ExportCGToCSV:** Gathers all CG (heaviest renders scheduled for out-of-hours rendering) jobs on the farm an hour before E.O.D., processes data from those jobs into human-readable information, then stores it in a CSV file sent to production. This helps point out anomalies and predict farm usage out of office hours.
- **FarmNotificationSystem:** Notifies stakeholders about their highest priority jobs on the farm. It uses Deadline and Shotgrid APIs to contact the correct people, then sends canned emails with relevant information. This was highly praised by production staff for streamlining communication about their most important jobs and freeing up my time for other tasks.
- **GetAvgSelectedCGFrameTime:** A quick and straightforward method for getting average render times for selected jobs.
- **RestartHolidayUsers:** Uses Shotgrid and Deadline APIs to determine if a user is on holiday or on set, and if they have left their computer logged on. If these conditions are met, it restarts their machine.
- **SplitMachineModify and SplitMachineModifyUI:** Handles the behavior of "split" machines, which are divided into multiple workers. This script enables and disables the "splits" depending on farm demands. The UI allows the wrangler to do this manually.

Thank you for taking the time to view my portfolio.
