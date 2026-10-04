---
source_ids:
- cloudflare-os-your-company-s-agent-workspace-man-32af5c2a
content_mode: verbatim
label: VERBATIM
---

[Cloudflare OS](https://os.cloudflare.app/) gives everyone in your organization an agent workspace that knows how your company works and connects to its data and systems. Today, we're opening the [waitlist](http://cloudflare.com/resource/cloudflare-os-managed/) for fully managed Cloudflare OS deployments.

If I asked you to prepare for an important customer meeting later today, what would you do? You might learn how your company typically runs customer meetings, review the account in your CRM, check recent support tickets and product usage, then turn it into a short presentation to review with the group. Now imagine doing that another 100 times this month.

Every team has work like this. With Cloudflare OS, you can ask your agent to handle the work for you, build a tool for your team, or move between the two as the work evolves.

Last month, we [announced](https://blog.cloudflare.com/cloudflare-os/) Cloudflare OS and shared the [open source repository](https://github.com/cloudflare/cloudflare-os). Since then, thousands of organizations have started using it to work with company data, produce docs and slides, build tools for their teams, and automate work with agents.

With a few clicks in the Cloudflare dashboard, you’ll be able to launch your organization’s own agent workspace. Just tell us what custom domain you want to use, what [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/) policies apply, and which [AI Gateway](https://www.cloudflare.com/products/ai-gateway/) to connect. We’ll handle the rest.

## Cloudflare OS, managed for you

Every company has its own terminology, procedures, systems, and requirements. We made Cloudflare OS [open source](https://github.com/cloudflare/cloudflare-os) so you can customize it around how your company works.

You can already deploy Cloudflare OS into your own Cloudflare account from the [open-source repository](https://github.com/cloudflare/cloudflare-os). That gives you full control, but it also means someone has to configure the deployment, operate it, and keep it up to date.

With the fully managed option, you decide who can access Cloudflare OS, which organizational skills and context are available, and which systems it can reach. You can leave the rest to us.

If you want Cloudflare OS fully managed for your organization, [join the waitlist](http://cloudflare.com/resource/cloudflare-os-managed/) and we’ll reach out.

## What’s new in Cloudflare OS

We’ve also spent the last month expanding what people and agents can do in Cloudflare OS. Here are a few highlights.

### Mount Git repos and work with code

When we launched Cloudflare OS, we focused first on work outside software development: creating documents and slides, automating tasks, and building collaborative tools. Agents could write code for an app, but they could not work with code in an existing Git repository.

You can now connect an existing GitHub repository to Cloudflare OS. Ask your agent to explore the codebase, fix a bug, add a feature, or open a pull request. It can search and edit files, review its changes, create commits, and push them to GitHub.

### Work across Google Workspace

For many organizations, work starts and ends in Google Workspace. Decisions live in email threads, context lives in Google Drive, analysis happens in Sheets, and teams coordinate through Calendar. Agents need to do work across those systems too.

We’ve made significant improvements to the Google Workspace [Gatekeeper](https://blog.cloudflare.com/cloudflare-os/#gatekeepers-govern-resources-and-actions) (a service-specific [Worker](https://developers.cloudflare.com/workers/?_gl=1*1pzndf6*_gcl_au*MzM2MDkxNTQzLjE3ODQ4NDczOTM.*_ga*MWVkZWU3OTctMzJjNC00YWE1LWI2ZDUtZTJkNTY1NzYxYWQ0*_ga_SQCRB0TXZW*czE3ODUyMTk3NjMkbzckZzAkdDE3ODUyMTk3NjMkajYwJGwwJGgwJGRQeHAyTUEtdzgtVUFETUEzOGwtVFVhajVDd2laRWYxSC1R&cf_page=cloudflare-os%2F) that sits between Cloudflare OS and an external service). Cloudflare OS can now read and research Gmail threads, create drafts, and send emails. You can also connect your entire Google Drive, a specific folder, or an individual doc or sheet.

### Export work in the formats your team uses

Work often needs to move into the formats your team already uses. Finance may need an Excel spreadsheet, and a report may need to become a PDF before sending to a customer.

The built-in document, presentation, and spreadsheet experiences can now export work to familiar formats. Depending on what you create, you can export to Microsoft Excel (.xlsx), CSV, PDF, Markdown, or HTML. Microsoft Word (.docx) and PowerPoint (.pptx) export is coming soon.

Tools you build can also define their own export formats. Tell the agent what you need, like “let me download this schedule as a calendar file (.ics)”, and it’ll add the option to the tool’s export menu.

## Sign up for the waitlist

Cloudflare OS is open source and available today. You can check out the [source code](https://github.com/cloudflare/cloudflare-os) or deploy it into your own Cloudflare account.

If you want Cloudflare OS fully managed for your organization, [join the waitlist](http://cloudflare.com/resource/cloudflare-os-managed/) and we’ll reach out with more information.
