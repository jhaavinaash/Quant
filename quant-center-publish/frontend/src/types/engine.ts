export interface EngineStatus {
  Timestamp: string;
  Engine: string;
  Status: 'SUCCESS' | 'FAILED';
  Detail: string;
}