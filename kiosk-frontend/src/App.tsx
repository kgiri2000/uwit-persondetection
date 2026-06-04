import React from 'react'
import { useRoomStore } from './store/useRoomStore'
import { LoginScreen } from './components/LoginScreen'
import { RoomDashboard } from './components/RoomDashboard'

export const App: React.FC = () => {
  const { isAuthenticated } = useRoomStore()

  return (
    <div className="w-screen h-screen overflow-hidden bg-uw-darkBg">
      {isAuthenticated ? <RoomDashboard /> : <LoginScreen />}
    </div>
  )
}

export default App
