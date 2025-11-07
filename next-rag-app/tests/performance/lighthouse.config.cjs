module.exports = {
  ci: {
    collect: {
      url: [
        process.env.LIGHTHOUSE_URL || 'https://rni-llm-01.lab.sensus.net',
      ],
      numberOfRuns: 1,
      settings: {
        formFactor: 'desktop',
        screenEmulation: { mobile: false },
      },
    },
    upload: {
      target: 'filesystem',
      outputDir: 'lighthouse-report',
    },
  },
};
