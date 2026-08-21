import { createRouter, createWebHistory } from 'vue-router';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/forms' },
    { path: '/forms/:id?', name: 'forms', component: () => import('./views/FormsView.vue') },
    {
      path: '/processes/:id?',
      name: 'processes',
      component: () => import('./views/ProcessesView.vue'),
    },
    {
      path: '/matrix/:id?',
      name: 'matrix',
      component: () => import('./views/MatrixView.vue'),
    },
  ],
});
