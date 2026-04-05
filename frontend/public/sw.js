// Service Worker for Web Push notifications
// Handles push events and shows browser notifications

self.addEventListener('push', function(event) {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'Info Platform', body: event.data ? event.data.text() : 'New digest ready' };
  }

  const title = data.title || 'Info Platform';
  const options = {
    body: data.body || 'A new digest has been generated.',
    icon: '/favicon.ico',
    badge: '/favicon.ico',
    tag: 'digest-notification',
    renotify: true,
    data: { url: data.url || '/digests' },
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/digests';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (const client of clientList) {
        if (client.url.includes(url) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});

self.addEventListener('install', function() {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(clients.claim());
});
