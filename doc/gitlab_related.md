# Gitlab considerations

The FAIRagro advanced middleware API will access the gitlab API (in case you use
the `GitlabApi` `ArcStore`) via https. Therefore it needs a group access token.

To prepare your Gitlab/Datahub instance to interoperate with the FAIRagro advanced
middle, please perform the following steps:

1. Create a private Gitlab group
2. Navigate to the group settings and create a group access token with the following
   features:

   * scopes: api, write_repository
   * role: maintainer

3. Add the add group (as well as the URL of your DataHub instance) to your FAIRagro
   advanced middleware config file
4. Define the environment variable `GITLAB_API_TOKEN` and assign the created group
   access token. Note: for testing purpose you may create a corresponding `.env` file
   in the project main directory.
