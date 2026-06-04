import React from 'react'
import { useRoomStore } from '../store/useRoomStore'
import { VideoPlayer } from './VideoPlayer'

export const GuestShelf: React.FC = () => {
  const { remoteStreams, localStream, role, userName } = useRoomStore()

  const remoteGuests = remoteStreams.filter((peer) => peer.role === 'guest')
  const showLocalGuest = role === 'guest' && localStream

  const totalGuestsCount = remoteGuests.length + (showLocalGuest ? 1 : 0)

  if (totalGuestsCount === 0) return null

  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 flex gap-3 p-3 bg-black/70 backdrop-blur-md rounded-2xl max-w-[90vw] overflow-x-auto shadow-2xl border border-gray-800 transition-all duration-300">
      {showLocalGuest && (
        <div className="w-[180px] h-[110px] shrink-0">
          <VideoPlayer
            stream={localStream}
            label={userName ? `${userName} (You)` : 'GUEST (You)'}
            muted={true}
            isLocal={true}
          />
        </div>
      )}
      {remoteGuests.map((peer) => (
        <div key={peer.id} className="w-[180px] h-[110px] shrink-0">
          <VideoPlayer
            stream={peer.stream}
            label={`${peer.name} (${peer.role.toUpperCase()})`}
            muted={false}
          />
        </div>
      ))}
    </div>
  )
}
