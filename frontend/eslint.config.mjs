import pluginVue from 'eslint-plugin-vue'
import vueTsConfig from '@vue/eslint-config-typescript'

export default [
  // Vue 3 specific rules (vue3-essential catches real bugs only)
  ...pluginVue.configs['flat/recommended'],
  ...vueTsConfig(),
  {
    rules: {
      // Vue 3 uses v-model:prop syntax — this is VALID in Vue 3
      'vue/no-v-model-argument': 'off',
      // Relax multi-word component names for small projects
      'vue/multi-word-component-names': 'off',
      // Allow kebab-case event names
      'vue/custom-event-name-casing': 'off',
      // Keep components self-closing
      'vue/html-self-closing': ['warn', { html: { void: 'always', normal: 'never', component: 'always' } }],
    },
  },
]
