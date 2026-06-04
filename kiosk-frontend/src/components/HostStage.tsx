import React from 'react'
import { useRoomStore } from '../store/useRoomStore'
import { VideoPlayer } from './VideoPlayer'

interface HostStageProps {
  localVideoRef: React.RefObject<HTMLVideoElement | null>
}

export const HostStage: React.FC<HostStageProps> = ({ localVideoRef }) => {
  const { remoteStreams, localStream, role, aiStatus, userName } = useRoomStore()

  const remoteHosts = remoteStreams.filter((peer) => peer.role === 'host')
  const showLocalHost = role === 'host' && localStream

  const totalHostsCount = remoteHosts.length + (showLocalHost ? 1 : 0)

  // CSS Grid class depending on how many hosts are in the room
  const gridClass = totalHostsCount >= 2 ? 'grid-cols-2' : 'grid-cols-1'

  return (
    <div className={`w-full h-full p-4 gap-4 grid ${gridClass} transition-all duration-500 ease-in-out`}>
      {showLocalHost && (
        <VideoPlayer
          stream={localStream}
          label={userName ? `${userName} (You)` : 'HOST (You)'}
          muted={true}
          isLocal={true}
          aiStatus={aiStatus}
          videoRef={localVideoRef}
        />
      )}
      {remoteHosts.map((peer) => (
        <VideoPlayer
          key={peer.id}
          stream={peer.stream}
          label={`${peer.name} (${peer.role.toUpperCase()})`}
          muted={false}
        />
      ))}
      {totalHostsCount === 0 && (
        <div className="flex flex-col items-center justify-center text-gray-500 border border-dashed border-gray-800 rounded-2xl h-full w-full">
          <p className="text-xl">No active hosts inside the room.</p>
          <p className="text-sm mt-2 text-gray-600">Start the kiosk connection to register as a host.</p>
        </div>
      )}
    </div>
  )
}
