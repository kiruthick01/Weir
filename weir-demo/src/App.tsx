import { WeirProvider } from './state/WeirProvider'
import { useWeir } from './state/useWeir'

function DemoLoaded() {
  const { state } = useWeir()

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 p-8 text-zinc-100">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900 px-8 py-6 shadow-2xl">
        Weir loaded — {state.approvers.length} approvers
      </div>
    </main>
  )
}

export default function App() {
  return (
    <WeirProvider>
      <DemoLoaded />
    </WeirProvider>
  )
}
