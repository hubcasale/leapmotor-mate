import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './assets/main.css'

// Apply saved theme immediately to avoid flash
const savedTheme = localStorage.getItem('theme')
if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme)

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
