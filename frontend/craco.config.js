module.exports = {
  style: {
    postcss: {
      mode: "file",
    },
  },
  devServer: (devServerConfig) => {
    devServerConfig.client = devServerConfig.client || {};
    devServerConfig.client.overlay = {
      errors: true,
      warnings: false,
      // Hide the runtime-error overlay for errors thrown by browser extensions (not our code).
      runtimeErrors: (error) => {
        const blob = `${error?.message || ""} ${error?.stack || ""} ${error?.filename || ""}`;
        return !/-extension:\/\//.test(blob);
      },
    };
    return devServerConfig;
  },
};
