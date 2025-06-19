import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 3000,
		host: '0.0.0.0',
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
				secure: false,
				rewrite: (path) => path
			},
			'/ws': {
				target: 'ws://localhost:8000',
				ws: true,
				changeOrigin: true
			}
		}
	},
	preview: {
		port: 3000,
		host: '0.0.0.0',
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
				secure: false
			},
			'/ws': {
				target: 'ws://localhost:8000',
				ws: true,
				changeOrigin: true
			}
		}
	}
});