export class GatewayRequestError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "GatewayRequestError";
    this.status = status;
  }
}
