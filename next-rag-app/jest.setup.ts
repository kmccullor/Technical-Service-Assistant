// Global test setup polyfills
if (typeof (global as any).Response === 'undefined') {
  (global as any).Response = class ResponsePolyfill {
    private _body: any
    status: number
    ok: boolean
    headers: Record<string,string>
    constructor(body: any = '{}', init: any = { status: 200 }) {
      this._body = body
      this.status = init.status || 200
      this.ok = this.status >= 200 && this.status < 300
      this.headers = init.headers || {}
    }
    async json() { try { return JSON.parse(this._body) } catch { return {} } }
    async text() { return String(this._body) }
  } as any
}
