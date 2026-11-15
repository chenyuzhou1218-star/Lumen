export class Bus {
  constructor() { this.handlers = {}; }
  on(name, fn) { (this.handlers[name] = this.handlers[name] || []).push(fn); }
  emit(name, data) { (this.handlers[name] || []).forEach((fn) => fn(data)); }
}
export const bus = new Bus();
