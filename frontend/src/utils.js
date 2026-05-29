export function shortModelName(model) {
  const idx = model.indexOf('/');
  return idx !== -1 ? model.substring(idx + 1) : model;
}
