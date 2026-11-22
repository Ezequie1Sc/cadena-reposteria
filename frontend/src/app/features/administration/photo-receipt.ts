import type { Photo } from './administration-api';
export function rememberPhoto(photo: Photo) {
  try {
    sessionStorage.setItem(
      'dg-photo-' + photo.producto_id,
      JSON.stringify({
        producto_id: photo.producto_id,
        imagen_id: photo.imagen_id,
        url: photo.url,
      }),
    );
  } catch {
    /* El recibo sigue disponible en la respuesta. */
  }
}
