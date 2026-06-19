export function Loading() {
  return (
    <div className="flex items-center justify-center h-48">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-red border-t-transparent" />
    </div>
  );
}

export function Err({ message }: { message: string }) {
  return (
    <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
      Failed to load data: {message}
    </div>
  );
}
