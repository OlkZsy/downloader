# How to invite another person to the project

There are two standard ways to collaborate on a GitHub repository.

## Option 1. Add a collaborator (full write access)

Suitable when you trust the person and want them to commit directly to
the repository.

1. Open the repository on GitHub (e.g.
   `https://github.com/OlkZsy/downloader`).
2. Go to the **Settings** tab (the gear in the repository's top menu).
3. Pick **Collaborators** on the left (the *Access* section). GitHub
   may ask you to confirm your password or a code.
4. Press the green **Add people** button.
5. Enter the person's **GitHub username** (or e-mail) and select them
   in the list.
6. Press **Add … to this repository**.
7. The person receives an invitation by e-mail and in their GitHub
   notifications — they must press **Accept invitation**. There is no
   access until the invitation is accepted.

After that the collaborator can clone the repository and push changes:

```bash
git clone https://github.com/OlkZsy/downloader.git
cd downloader
# ... edits ...
git add -A
git commit -m "Describe the change"
git push
```

> Tip: even with two participants it pays off to work through branches
> and pull requests instead of committing straight to `main` — changes
> can then be reviewed before merging.

## Option 2. Fork + Pull Request (no access granted)

Suitable for external contributors: they need no access to your
repository at all.

The contributor:

1. Presses **Fork** on your repository page — they get their own copy.
2. Clones their fork, creates a branch and makes the changes:
   ```bash
   git clone https://github.com/CONTRIBUTOR_NAME/downloader.git
   cd downloader
   git checkout -b add-soundcloud
   # ... edits ...
   git commit -am "Add the SoundCloud plugin"
   git push -u origin add-soundcloud
   ```
3. Presses **Compare & pull request** on GitHub and submits the PR to
   your repository.

You:

1. Open the **Pull requests** tab of your repository.
2. Review the changes (the *Files changed* tab), leaving comments where
   needed.
3. Press **Merge pull request** once everything looks good.

## Useful settings for collaboration

- **Settings → Branches → Add branch ruleset**: protect the `main`
  branch by requiring a pull request before merging.
- **Issues**: enable the Issues tab (Settings → General → Features) to
  track tasks and bugs right in the repository.
- Tasks for new contributors are best described in Issues and labeled
  `good first issue`.
