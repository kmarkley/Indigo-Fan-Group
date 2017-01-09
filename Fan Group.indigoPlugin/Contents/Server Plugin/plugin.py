#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# http://www.indigodomo.com

import indigo
import time

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

###############################################################################
# globals

kSpeedIndex = {
    0:  'off',
    1:  'low',
    2:  'medium',
    3:  'high',
    }

################################################################################
class Plugin(indigo.PluginBase):
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
    
    def __del__(self):
        indigo.PluginBase.__del__(self)

    ########################################
    # Start, Stop and Config changes
    ########################################
    def startup(self):
        self.debug = self.pluginPrefs.get('showDebugInfo',False)
        self.logger.debug("startup")
        if self.debug:
            self.logger.debug("Debug logging enabled")
        self.deviceDict = dict()
        indigo.devices.subscribeToChanges()

    ########################################
    def shutdown(self):
        self.logger.debug("shutdown")
        self.pluginPrefs['showDebugInfo'] = self.debug

    ########################################
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.logger.debug("closedPrefsConfigUi")
        if not userCancelled:
            self.debug = valuesDict.get("showDebugInfo",False)
            if self.debug:
                self.logger.debug("Debug logging enabled")

    ########################################
    def validatePrefsConfigUi(self, valuesDict):
        self.logger.debug("validatePrefsConfigUi")
        errorsDict = indigo.Dict()
                
        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)
    
    ########################################
    def runConcurrentThread(self):
        self.logger.debug("runConcurrentThread")
        try:
            while True:
                loopTime = time.time()
                for devId in self.deviceDict:
                    dev = self.deviceDict[devId]['dev']
                    if dev.deviceTypeId == 'thermAssist' and dev.onState and self.deviceDict[devId]['nextTemp']:
                        if self.deviceDict[devId]['nextTemp'] < loopTime:
                            therm = self.deviceDict[devId]['therm']
                            self.logger.debug("thermostat status request: "+therm.name)
                            indigo.device.statusRequest(therm.id, suppressLogging=(not self.debug))
                            self.deviceDict[devId]['nextTemp'] = loopTime + int(dev.pluginProps['tempFreq'])
                self.sleep(loopTime+10-time.time())
        except self.StopThread:
            pass    # Optionally catch the StopThread exception and do any needed cleanup.
    
    
    ########################################
    # Device Methods
    ########################################
    def deviceStartComm(self, dev):
        self.logger.debug("deviceStartComm: "+dev.name)
        if dev.version != self.pluginVersion:
            self.updateDeviceVersion(dev)
        if dev.id not in self.deviceDict:
            theProps = dev.pluginProps
            fanDict = {}
            for fanId in theProps.get('fans',[]):
                fanDict[int(fanId)] = indigo.devices[int(fanId)]
            thermId = int(theProps.get('thermostat',"0"))
            if thermId:
                therm = indigo.devices[thermId]
                nextTemp = time.time() + int(theProps.get('tempFreq',"300"))
            else:
                therm = None
                nextTemp = None
            self.deviceDict[dev.id] = {'dev':dev, 'fanDict':fanDict, 'therm':therm, 'nextTemp':nextTemp}
    
    ########################################
    def deviceStopComm(self, dev):
        self.logger.debug("deviceStopComm: "+dev.name)
        if dev.id in self.deviceDict:
            del self.deviceDict[dev.id]
    
    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, devId, runtime=False):
        self.logger.debug("validateDeviceConfigUi: " + typeId)
        errorsDict = indigo.Dict()
        
        if typeId == 'thermAssist':
            for key in ['onThreshhold','offThreshhold']:
                if valuesDict.get(key,"") == "":
                    errorsDict[key] = "Required"
                else:
                    try: 
                        t = float(valuesDict[key])
                        if t <= 0.0:
                            raise
                    except: 
                        errorsDict[key] = "Must be positive real number"
            if float(valuesDict['offThreshhold']) > float(valuesDict['offThreshhold']):
                errorsDict['offThreshhold'] = "Must be less than or equal to ON Threshhold"
        
        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        else:
            return (True, valuesDict)
    
    ########################################
    def updateDeviceVersion(self, dev):
        theProps = dev.pluginProps
        # update states
        dev.stateListOrDisplayStateIdChanged()
        # check for changed props
        
        # push to server
        theProps["version"] = self.pluginVersion
        dev.replacePluginPropsOnServer(theProps)
    
    ########################################
    def updateDeviceStatus(self, dev, thermFlag=False):
        self.logger.debug("updateDeviceStatus: " + dev.name)
        theProps = dev.pluginProps
        fanDict = self.deviceDict[dev.id]['fanDict']
        
        if not fanDict:
            # this is a dummy fan
            pass
        
        elif dev.deviceTypeId == "fanGroupFull":
            statusLogic = theProps.get('statusLogic',"avg")
            if statusLogic == "avg":
                fanIndex = 0.0
                for fanId, fan in fanDict.items():
                    fanIndex += fan.speedIndex
                dev.updateStateOnServer(key='speedIndex', value=(int(round(fanIndex/len(fanDict)))))
            elif statusLogic == "min":
                fanLevel = min(fan.speedLevel for fanId, fan in fanDict.items())
                dev.updateStateOnServer(key='speedLevel', value=fanLevel)
            elif statusLogic == "max":
                fanLevel = max(fan.speedLevel for fanId, fan in fanDict.items())
                dev.updateStateOnServer(key='speedLevel', value=fanLevel)
            elif statusLogic == "all":
                for i in range(4):
                    if all(fan.speedIndex == i for fanId, fan in fanDict.items()):
                        dev.updateStateOnServer(key='speedIndex', value=i)
                        break
                else:
                    dev.updateStateOnServer(key='speedIndex', value=0)
        
        elif dev.deviceTypeId == "fanGroupSimple":
            if any(fan.speedLevel > 0 for fanId, fan in fanDict.items()):
                dev.updateStateOnServer(key='onOffState', value=True)
            else:
                dev.updateStateOnServer(key='onOffState', value=False)
        
        elif dev.deviceTypeId == "thermAssist" and thermFlag:
            therm = self.deviceDict[dev.id]['therm']
            coolDelta = therm.temperatures[0] - therm.coolSetpoint
            heatDelta = therm.heatSetpoint - therm.temperatures[0]
            tempDelta = max([coolDelta,heatDelta])
            onLimit   = tempDelta > float(theProps['onThreshhold'])
            offLimit  = tempDelta > float(theProps['offThreshhold']) and dev.onState
            onFlag    = (therm.coolIsOn or therm.heatIsOn) and (onLimit or offLimit)
            
            onLevel   = int(theProps['onLevel'])
            allOn     = all(fan.speedIndex == onLevel for fanId, fan in fanDict.items())
            allOff    = all(fan.speedIndex == 0       for fanId, fan in fanDict.items())
            
            if onFlag and not dev.onState:
                if theProps['onOverride'] or allOff:
                    self.setGroupSpeedIndex(dev, onLevel)
                    dev.updateStateOnServer(key='onOffState', value=True)
                    self.deviceDict[dev.id]['nextTemp'] = time.time() + int(theProps['tempFreq'])
            elif not onFlag and dev.onState:
                dev.updateStateOnServer(key='onOffState', value=False)
                if theProps['offOverride'] or allOn:
                    self.setGroupSpeedIndex(dev, 0)
    
    ########################################
    # Device updated
    ########################################
    def deviceUpdated(self, oldDev, newDev):
        if (oldDev.pluginId == self.pluginId) or (newDev.pluginId == self.pluginId):
            indigo.PluginBase.deviceUpdated(self, oldDev, newDev)
        
        elif isinstance(newDev, indigo.SpeedControlDevice) and (newDev.speedLevel != oldDev.speedLevel):
            for devId in self.deviceDict:
                fanDict = self.deviceDict[devId]['fanDict']
                for fanId, fan in fanDict.items():
                    if newDev.id == fanId:
                        self.logger.debug("deviceUpdated: "+newDev.name)
                        # keep a copy of the updated fan
                        self.deviceDict[devId]['fanDict'][fanId] = newDev
                        # update the fan group device
                        self.updateDeviceStatus(self.deviceDict[devId]['dev'])
                        break
                    
        elif isinstance(newDev, indigo.ThermostatDevice) and (newDev.states != oldDev.states):
            for devId in self.deviceDict:
                therm = self.deviceDict[devId]['therm']
                if therm and (newDev.id == therm.id):
                    self.logger.debug("deviceUpdated: "+newDev.name)
                    # keep a copy of the updated thermostat
                    self.deviceDict[devId]['therm'] = newDev
                    # update the fan group device
                    self.updateDeviceStatus(self.deviceDict[devId]['dev'], True)
    
    ########################################
    # Action Methods
    ########################################
    def actionControlSpeedControl(self, action, dev):
        self.logger.debug("actionControlSpeedControl: "+dev.name)
        if action.speedControlAction == indigo.kSpeedControlAction.SetSpeedIndex:
            self.logger.info('"%s" set motor speed to %s' % (dev.name, kSpeedIndex[action.actionValue]))
            self.setGroupSpeedIndex(dev, action.actionValue)
        elif action.speedControlAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info('"%s" status update' % dev.name)
            self.updateDeviceStatus(dev)
        else:
            self.logger.error("Unknown action: "+unicode(action.speedControlAction))
    
    ########################################
    def actionControlDimmerRelay(self, action, dev):
        self.logger.debug("actionControlDimmerRelay: "+dev.name)
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            self.logger.info('"%s" on' % dev.name)
            self.setGroupSpeedIndex(dev, int(dev.pluginProps.get('onLevel',1)))
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            self.logger.info('"%s" off' % dev.name)
            self.setGroupSpeedIndex(dev, 0)
        elif action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info('"%s" status update' % dev.name)
            self.updateDeviceStatus(dev)
        else:
            self.logger.error("Unknown action: "+unicode(action.deviceAction))
    
    ########################################
    def actionControlSensor(self, action, dev):
        self.logger.debug(u"actionControlSensor: "+dev.name)
        if action.sensorAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info('"%s" status request' % dev.name)
            self.updateDeviceStatus(dev)
        else:
            self.logger.error("Unknown action: "+unicode(action.sensorAction))
    
    ########################################
    # Menu Methods
    ########################################
    def toggleDebug(self):
        if self.debug:
            self.logger.debug("Debug logging disabled")
            self.debug = False
        else:
            self.debug = True
            self.logger.debug("Debug logging enabled")
        
    ########################################
    # Menu Callbacks
    ########################################
    def getSpeedControlDeviceList(self, filter="", valuesDict=None, typeId="", targetId=0):
        devList = []
        excludeList  = [dev.id for dev in indigo.devices.iter(filter='self')]
        for dev in indigo.devices.iter(filter='indigo.speedcontrol'):
            if not dev.id in excludeList:
                devList.append((dev.id, dev.name))
        return devList        
        
    ########################################
    # Utilities
    ########################################
    def setGroupSpeedIndex(self, dev, speedIndex):
        fanDict = self.deviceDict[dev.id]['fanDict']
        if fanDict:
            for fanId, fan in fanDict.items():
                if fan.speedIndex != speedIndex:
                    indigo.speedcontrol.setSpeedIndex(fanId, value=speedIndex)
        else: # this is a dummy fan
            dev.updateStateOnServer(key='speedIndex', value=speedIndex)
    