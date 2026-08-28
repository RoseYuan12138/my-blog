# Blog Workspace Instructions

This workspace is the user's personal blog repository.

- GitHub repository: https://github.com/RoseYuan12138/my-blog
- Git remote: `origin`
- Primary branch: `v4`
- Blog and learning content is mainly stored in `content/`.
- The user expects to update learning notes and other blog information here frequently.

## Normal update workflow

When the user asks to update or publish the blog:

1. Check the working tree and preserve any uncommitted user changes.
2. Pull the latest `origin/v4` before editing when it is safe to do so.
3. Make the requested content changes in this workspace.
4. Review and verify the changes as appropriate.
5. Commit with a clear message and push to `origin/v4` when the user asks to publish, upload, or "往上推".

Do not overwrite unrelated local work. The local `tmp/` directory is excluded through `.git/info/exclude` and should not be committed.
