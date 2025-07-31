from CollideObjectBase import SphereCollideObject
from panda3d.core import Loader, NodePath, Vec3, Filename, CollisionSphere, ClockObject
from direct.task.Task import TaskManager, Task
from typing import Callable
from SpaceJamClasses import Drone, Missile
import math, random, re
from direct.interval.LerpInterval import LerpFunc
from direct.particles.ParticleEffect import ParticleEffect
from panda3d.core import CollisionHandlerEvent


class Spaceship(SphereCollideObject):
    def __init__(self, loader: Loader, taskMgr, accept: Callable[[str, Callable], None], 
                 modelPath: str, parentNode: NodePath, nodeName: str, texPath: str, 
                 posVec: Vec3, scaleVec: float, camera, traverser, handler):

        super().__init__(loader, modelPath, parentNode, nodeName, Vec3(0, 0, 0), 0.01)
        
        # Setup basic model
        self.modelNode.setPos(posVec)
        self.modelNode.setScale(scaleVec)
        self.modelNode.setName(nodeName)
        self.modelNode.setHpr(0, -90, 0)
        self.collisionNode.show()

        tex = loader.loadTexture(texPath)
        self.modelNode.setTexture(tex, 1)

        # Init handlers and references
        self.loader = loader
        self.render = parentNode
        self.accept = accept
        self.traverser = traverser
        self.handler = CollisionHandlerEvent()
        self.handler.addInPattern('into')
        self.accept('into', self.HandleInto)

        self.taskMgr = taskMgr
        self.camera = camera
       
        # Movement and physics
        self.velocity = Vec3(0, 0, 0)
        self.base_acceleration = 50
        self.acceleration_magnitude = self.base_acceleration
        self.base_speed = 500
        self.current_speed = self.base_speed
        self.max_speed = 3000
        self.damping = 0.99

        # Boost
        self.boost_multiplier = 10
        self.boost_duration = 10
        self.boost_cooldown = 5
        self.can_boost = True
        self.boost_status_callback = None

        # Missile firing
        self.reloadTime = 0.25
        self.missileDistance = 4000
        self.missileBay = 10   # total missiles available in bay
        self.missilesLeft = self.missileBay  # track current missiles left to display on UI
        self.taskMgr.add(self.CheckIntervals, 'checkMissiles', 34)
        self.missileTextRef = None  # UI text object reference
        
        # Particles
        self.SetParticles()
        self.cntExplode = 0
        self.explodeIntervals = {}

        #Sound 
        self.engineSound = loader.loadSfx("./Assets/Sound/engine.mp3")  
        self.rocketSound = loader.loadSfx("./Assets/Sound/rocket.mp3")
        self.explosionSound = loader.loadSfx("./Assets/Sound/explosion.mp3")

        self.engineSound.setLoop(True)
        self.engineSound.setVolume(0.4)
        # Camera
        self.zoom_factor = 5
        self.cameraZoomSpeed = 10

        # Clock
        self.globalClock = ClockObject.getGlobalClock()

        # Task for movement
        self.taskMgr.add(self.UpdateMovement, "update-movement")

    # Link the missile count UI text to update dynamically
    def setMissileTextRef(self, textObj):
        self.missileTextRef = textObj
        self.updateMissileUI()

    def updateMissileUI(self):
        if self.missileTextRef:
            self.missileTextRef.setText(f"Missiles: {self.missilesLeft}")

    def SetParticles(self):
        self.explodeEffect = ParticleEffect()
        self.explodeEffect.loadConfig("./Assets/Part-Efx/basic_xpld_efx.ptf")
        self.explodeEffect.setScale(50)
        self.explodeNode = self.render.attachNewNode('ExplosionEffects')

    def Explode(self):
        self.cntExplode += 1
        tag = 'particles-' + str(self.cntExplode)
        self.explodeIntervals[tag] = LerpFunc(self.ExplodeLight, duration=4.0)
        self.explodeIntervals[tag].start()

    def ExplodeLight(self, t):
        if t == 1.0 and self.explodeEffect:
            self.explodeEffect.disable()
        elif t == 0:
            print(f"Starting particle at {self.explodeNode.getPos()}")

        # Stop previous effect if still running
        self.explodeEffect.disable()

        # Reparent particle effect to explosion node to follow its position
        self.explodeEffect.reparentTo(self.explodeNode)

        # Reset particle effect to origin of explodeNode so it appears at explodeNode's position
        self.explodeEffect.setPos(0, 0, 0)

        # Start particle effect
        self.explodeEffect.start(self.explodeNode)


    def Boost(self):
        if not self.can_boost:
            print("Boost is on cooldown!")
            if self.boost_status_callback:
                self.boost_status_callback("COOLDOWN")
            return

        self.can_boost = False
        self.acceleration_magnitude = self.base_acceleration * self.boost_multiplier
        print("Boost activated! Acceleration multiplied.")
        if self.boost_status_callback:
            self.boost_status_callback("ACTIVE")

        self.taskMgr.doMethodLater(self.boost_duration, self.EndBoost, 'end-boost')

    def EndBoost(self, task):
        self.acceleration_magnitude = self.base_acceleration
        print("Boost ended. Acceleration back to normal.")
        if self.boost_status_callback:
            self.boost_status_callback("COOLDOWN")
        self.taskMgr.doMethodLater(self.boost_cooldown, self.ResetBoost, 'reset-boost')
        return Task.done

    def ResetBoost(self, task):
        self.can_boost = True
        print("Boost ready again.")
        if self.boost_status_callback:
            self.boost_status_callback("READY")
        return Task.done

    def move_forward(self, keyDown):
        if keyDown:
            if not self.taskMgr.hasTaskNamed('apply-thrust'):
                self.taskMgr.add(self.ApplyThrust, 'apply-thrust')
        else:
            if self.taskMgr.hasTaskNamed('apply-thrust'):
                self.taskMgr.remove('apply-thrust')

    def ApplyThrust(self, task):
        dt = self.globalClock.getDt()
        forward_vec = self.modelNode.getQuat().getForward()
        self.velocity += forward_vec * self.acceleration_magnitude * dt

        if self.velocity.length() > self.max_speed:
            self.velocity.normalize()
            self.velocity *= self.max_speed

        return Task.cont

    def UpdateMovement(self, task):
        dt = self.globalClock.getDt()

        self.velocity *= self.damping
        new_pos = self.modelNode.getPos() + self.velocity * dt
        self.modelNode.setPos(new_pos)

        # Check movement magnitude to determine if the ship is moving
        if self.velocity.length() > 0.1:
            if self.engineSound.status() != self.engineSound.PLAYING:
                self.engineSound.play()
        else:
            if self.engineSound.status() == self.engineSound.PLAYING:
                self.engineSound.stop()

        return Task.cont

    def CheckIntervals(self, task):
        for i in list(Missile.Intervals.keys()):
            if not Missile.Intervals[i].isPlaying():
                Missile.cNodes[i].detachNode()
                Missile.fireModels[i].detachNode()
                del Missile.Intervals[i]
                del Missile.fireModels[i]
                del Missile.cNodes[i]
                del Missile.collisionSolids[i]
                print(i + ' has ended.')
        return Task.cont

    def Fire(self):
        if self.missileBay > 0:
            travRate = self.missileDistance
            aim = self.render.getRelativeVector(self.modelNode, Vec3.forward())
            aim.normalize()
            fireSolution = aim * travRate
            inFront = aim * 150
            travVec = fireSolution + self.modelNode.getPos()

            tag = 'Missile' + str(Missile.missileCount)
            posVec = self.modelNode.getPos() + inFront
            currentMissile = Missile(self.loader, "./Assets/Phaser/phaser.egg", self.render, tag, posVec, 4.0)
            self.traverser.addCollider(currentMissile.collisionNode, self.handler)
            Missile.Intervals[tag] = currentMissile.modelNode.posInterval(2.0, travVec, startPos=posVec, fluid=1)
            Missile.Intervals[tag].start()

            self.missileBay -= 1
            self.missilesLeft -= 1
            self.updateMissileUI()
            self.rocketSound.play()
            print(f"Missile fired! {self.missileBay} remaining.")

            if self.missileBay == 0 and not self.taskMgr.hasTaskNamed('reload'):
                print('Ammo depleted. Reloading...')
                self.taskMgr.doMethodLater(self.reloadTime, self.Reload, 'reload')
        else:
            print('No missiles! Waiting for reload...')

    def Reload(self, task):
        self.missileBay = 10
        self.missilesLeft = 10
        self.updateMissileUI()
        print("Reload complete. Missiles replenished.")
        return Task.done

    def HandleInto(self, entry):
        fromNode = entry.getFromNodePath().getName()
        intoNode = entry.getIntoNodePath().getName()
        intoPosition = Vec3(entry.getSurfacePoint(self.render))

        shooter = fromNode.split('_')[0]
        victim = intoNode.split('_')[0]
        stripped = re.sub(r'[0-9]', '', victim)

        if stripped in ("Drone", "Planet", "Space Station"):
            print(f"{victim} hit at {intoPosition}")

        # Handle drone-specific destruction
        drone_found = False
        for drone in Drone.droneInstances:
            if drone.modelNode.getName() == victim:
                # Set explosion position to the drone's position
                explosionPos = drone.modelNode.getPos()
                self.explodeNode.setPos(explosionPos)
                
                # Call drone's explode method
                drone.explode()
                
                # Call the particle effect
                self.Explode()
                
                drone_found = True
                break

        # FIX: removed isDetached(), replaced with getParent().isEmpty()
        nodeID = self.render.find(victim)
        if not nodeID.isEmpty() and not nodeID.getParent().isEmpty():
            nodeID.detachNode()
        else:
            fullNode = self.render.find(intoNode)
            if not fullNode.isEmpty():
                fullNode.detachNode()

        self.explosionSound.play()

    def DestroyObject(self, hitID, hitPosition):
        nodeID = self.render.find(hitID)
        if not nodeID.isEmpty() and not nodeID.getParent().isEmpty():
            nodeID.detachNode()
        else:
            print(f"Warning: Node '{hitID}' not found or already detached.")
        
        self.explodeNode.setPos(hitPosition)
        self.Explode()

    def turn_left(self, keyDown):
        if keyDown:
            self.taskMgr.add(self.ApplyTurnLeft, 'turn-left')
        else:
            self.taskMgr.remove('turn-left')

    def ApplyTurnLeft(self, task):
        self.modelNode.setH(self.modelNode.getH() + 1.5)
        return Task.cont

    def turn_right(self, keyDown):
        if keyDown:
            self.taskMgr.add(self.ApplyTurnRight, 'turn-right')
        else:
            self.taskMgr.remove('turn-right')

    def ApplyTurnRight(self, task):
        self.modelNode.setH(self.modelNode.getH() - 1.5)
        return Task.cont

    def turn_up(self, keyDown):
        if keyDown:
            self.taskMgr.add(self.ApplyTurnUp, 'turn-up')
        else:
            self.taskMgr.remove('turn-up')

    def ApplyTurnUp(self, task):
        self.modelNode.setP(self.modelNode.getP() - 1.5)
        return Task.cont

    def turn_down(self, keyDown):
        if keyDown:
            self.taskMgr.add(self.ApplyTurnDown, 'turn-down')
        else:
            self.taskMgr.remove('turn-down')

    def ApplyTurnDown(self, task):
        self.modelNode.setP(self.modelNode.getP() + 1.5)
        return Task.cont

    def zoom_in(self, keyDown):
        if keyDown:
            self.taskMgr.add(self.ApplyZoomIn, 'zoom-in')
        else:
            self.taskMgr.remove('zoom-in')

    def ApplyZoomIn(self, task):
        self.camera.setPos(self.camera.getPos() + Vec3(0, self.cameraZoomSpeed, 0))
        return Task.cont

    def zoom_out(self, keyDown):
        if keyDown:
            self.taskMgr.add(self.ApplyZoomOut, 'zoom-out')
        else:
            self.taskMgr.remove('zoom-out')

    def ApplyZoomOut(self, task):
        self.camera.setPos(self.camera.getPos() + Vec3(0, -self.cameraZoomSpeed, 0))
        return Task.cont

    def attach_drone_rings(self, numDronesPerRing=12, radius=20):
        ringParent = self.modelNode.attachNewNode("AllDroneRings")
        angleStep = 2 * math.pi / numDronesPerRing

        for axis in ['x', 'y', 'z']:
            for i in range(numDronesPerRing):
                angle = i * angleStep
                pos = Vec3()
                if axis == 'x':
                    pos.y = math.cos(angle) * radius
                    pos.z = math.sin(angle) * radius
                elif axis == 'y':
                    pos.x = math.cos(angle) * radius
                    pos.z = math.sin(angle) * radius
                elif axis == 'z':
                    pos.x = math.cos(angle) * radius
                    pos.y = math.sin(angle) * radius

                Drone(
                    self.loader,
                    "./Assets/DroneDefender/DroneDefender.obj",
                    ringParent,
                    f"Drone-{axis}-{i}",
                    "./Assets/DroneDefender/octotoad1_auv.png",
                    pos,
                    .5
                )

    def set_boost_callback(self, callback):
        self.boost_status_callback = callback
